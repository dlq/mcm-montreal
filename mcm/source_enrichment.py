from __future__ import annotations

import re

from .source_types import SourceDefinition
from .source_utils import _clean_text, _normalize_lookup


def _extract_designer_and_maker(title: str, description: str) -> tuple[str, str]:
    match = re.search(r"(.+?)\s+pour\s+(.+?)(?:$|,|\||\.)", description, flags=re.IGNORECASE)
    if match:
        designer = _last_person_name(match.group(1))
        if designer:
            return designer, _clean_text(match.group(2))

    match = re.search(r"\bby\s+(.+?)(?:\s+for\s+(.+?))?$", title, flags=re.IGNORECASE)
    if match:
        designer = _clean_designer_candidate(match.group(1))
        maker = _clean_maker_candidate(match.group(2) or "")
        if designer:
            return designer, maker

    first_sentence = re.split(r"[.\n|]", description, maxsplit=1)[0]
    match = re.search(
        r"\bdesigned\s+by\s+(.+?)(?:,|\s+for\s+(.+?))?$",
        first_sentence,
        flags=re.IGNORECASE,
    )
    if match:
        designer = _clean_designer_candidate(match.group(1))
        maker = _clean_maker_candidate(match.group(2) or "")
        if designer:
            return designer, maker

    fallback = _clean_maker_candidate(description)
    return "", fallback if fallback and len(fallback.split()) < 6 else ""


def _clean_designer_candidate(value: str) -> str:
    candidate = _clean_text(value)
    if not candidate or len(candidate.split()) > 5:
        return ""
    if re.search(r"[.;:!?]", candidate):
        return ""
    return candidate


def _clean_maker_candidate(value: str) -> str:
    candidate = _clean_text(value)
    if not candidate:
        return ""
    if len(candidate.split()) > 6:
        return ""
    if re.search(
        r"\b(contactez-nous|contactez nous|details|détails|frais s’appliques|more information|checkout|shipping|policies)\b",
        candidate,
        re.I,
    ):
        return ""
    if re.search(r"\b(canada|montreal|montréal|ottawa)\b", candidate, re.I):
        return ""
    return candidate


def _extract_era(text: str) -> str:
    match = re.search(
        r"(?<!\w)(19[4-9]0[’']?s|20[0-2]0[’']?s|[’']\d0s)(?!\w)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        match = re.search(r"\bann[ée]es?\s+([4-9]0)\b", text, flags=re.IGNORECASE)
        if match:
            return f"19{match.group(1)}s"
    if not match:
        return ""
    value = match.group(1)
    if value.startswith(("'", "’")):
        return f"19{value[1:]}"
    return re.sub(r"[’']", "", value)


def _extract_dimensions(text: str) -> str:
    dimension_unit = r"(?:cm|in|\"|''|”|″)"
    dimension_label = r"[WLDHP]"
    dimension_part = (
        r"\d+(?:[.,]\d+)?\s*"
        rf"(?:(?:{dimension_unit})\s*)?"
        rf"{dimension_label}?"
    )
    match = re.search(
        rf"({dimension_part}\s*[xX]\s*{dimension_part}(?:\s*[xX]\s*{dimension_part})?)",
        text,
        flags=re.IGNORECASE,
    )
    if match and _has_dimension_signal(match.group(1)):
        return _clean_text(match.group(1))
    separated_dimension_part = (
        r"\d+(?:[.,]\d+)?\s*"
        rf"(?:(?:{dimension_unit})\s*)?"
        rf"{dimension_label}?"
        r"(?:\s*\([^)]{1,32}\))?"
    )
    match = re.search(
        rf"({separated_dimension_part})\s*[xX×]\s*"
        rf"({separated_dimension_part})(?:\s*[xX×]\s*({separated_dimension_part}))?",
        text,
        flags=re.IGNORECASE,
    )
    if match and _has_dimension_signal(" ".join(part for part in match.groups() if part)):
        parts = [re.sub(r"\s*\([^)]{1,32}\)", "", part).strip() for part in match.groups() if part]
        return _clean_text(" x ".join(parts))
    prefixed_french_dimensions = _extract_prefixed_french_dimensions(text)
    if prefixed_french_dimensions:
        return prefixed_french_dimensions
    french_labeled_dimensions = _extract_french_labeled_dimensions(text)
    if french_labeled_dimensions:
        return french_labeled_dimensions
    labeled_value = rf"(\d+(?:[.,]\d+)?)\s*({dimension_unit})?"
    match = re.search(
        rf"\b(?:largeur|longueur)\s*:?\s*{labeled_value}"
        rf".{{0,32}}?\bprofondeur\s*:?\s*{labeled_value}"
        rf".{{0,32}}?\bhauteur\s*:?\s*{labeled_value}",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        width, width_unit, depth, depth_unit, height, height_unit = match.groups()
        return _clean_text(
            f"{width}{width_unit or ''}L x "
            f"{depth}{depth_unit or ''}P x "
            f"{height}{height_unit or ''}H"
        )
    match = re.search(
        rf"(\d+(?:[.,]\d+)?\s*(?:{dimension_unit})?\s*Ø)"
        rf"\s*[xX×]\s*"
        rf"(\d+(?:[.,]\d+)?\s*(?:{dimension_unit})?\s*[HP])",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return _clean_text(f"{match.group(1)} x {match.group(2)}")
    labeled_dimensions = _extract_labeled_dimensions(text)
    if labeled_dimensions:
        return labeled_dimensions
    single_dimension = _extract_single_dimension(text)
    if single_dimension:
        return single_dimension
    match = re.search(r"\d+(?:\.\d+)?\s*[WLDH]\s*x?\s*\d+(?:\.\d+)?", text)
    return match.group(0) if match else ""


def _extract_prefixed_french_dimensions(text: str) -> str:
    prefix_pattern = re.compile(r"\b(?P<prefix>fauteuil|ottoman)\s*:", flags=re.IGNORECASE)
    matches = list(prefix_pattern.finditer(text))
    if len(matches) < 2:
        return ""
    dimensions: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        segment = text[match.end() : end]
        value = _extract_french_labeled_dimensions(segment)
        if value:
            dimensions.append(f"{match.group('prefix').capitalize()}: {value}")
    return "; ".join(dimensions) if len(dimensions) >= 2 else ""


def _extract_french_labeled_dimensions(text: str) -> str:
    label_pattern = re.compile(
        r"\b(?P<label>largeur|longueur|profondeur|hauteur)"
        r"(?P<context>\s*(?:\([^)]*\)|totale?)?)\s*:",
        flags=re.IGNORECASE,
    )
    matches = list(label_pattern.finditer(text))
    values: dict[str, str] = {}
    for index, match in enumerate(matches):
        raw_label = match.group("label").lower()
        context = (match.group("context") or "").lower()
        label = {"largeur": "L", "longueur": "L", "profondeur": "P", "hauteur": "H"}[raw_label]
        if label == "H" and re.search(r"\b(assise|dossier|abat-jour|mur)\b", context):
            continue
        segment_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        segment = text[match.end() : segment_end]
        value = _extract_french_dimension_value(segment)
        if value and label not in values:
            values[label] = value
    if not {"L", "P", "H"}.issubset(values):
        return ""
    return _clean_text(f"{values['L']}L x {values['P']}P x {values['H']}H")


def _extract_french_dimension_value(segment: str) -> str:
    segment = re.split(r"\s+-\s+|\.\s+", segment, maxsplit=1)[0]
    matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*(cm|in|\"|''|”|″)?", segment)
    if not matches:
        return ""
    unit = next((unit for _, unit in matches if unit), "")
    values = [f"{value}{item_unit or unit}" for value, item_unit in matches[:3]]
    if len(values) >= 2 and re.search(r"\b(?:et|à)\b|/|-", segment, flags=re.IGNORECASE):
        return "/".join(values)
    return values[0]


def _extract_labeled_dimensions(text: str) -> str:
    shorthand_pattern = re.compile(
        r"(?<![A-Z])(?P<label>[HWLDP])(?![A-Z])\.?\s*:?\s*"
        r"(?:approx(?:imately)?\.?\s*)?"
        r"(?P<value>\d+(?:[.,]\d+)?(?:\s*[-/]\s*\d+(?:[.,]\d+)?)?)\s*"
        r"(?P<unit>cm|in|\"|''|”|″)?",
        flags=re.IGNORECASE,
    )
    word_pattern = re.compile(
        r"\b(?P<label>length|width|depth|height)\s*"
        r"(?::|approx(?:imately)?\.?)?\s*"
        r"(?P<value>\d+(?:[.,]\d+)?(?:\s*[-/]\s*\d+(?:[.,]\d+)?)?)\s*"
        r"(?P<unit>cm|in|\"|''|”|″)?",
        flags=re.IGNORECASE,
    )
    matches: list[tuple[int, str, str, str]] = []
    for match in shorthand_pattern.finditer(text):
        label = match.group("label").upper()
        matches.append((match.start(), label, match.group("value"), match.group("unit") or ""))
    for match in word_pattern.finditer(text):
        prefix = text[max(0, match.start() - 12) : match.start()].lower()
        if "seat" in prefix or "back" in prefix:
            continue
        label = {
            "length": "L",
            "width": "W",
            "depth": "D",
            "height": "H",
        }[match.group("label").lower()]
        matches.append((match.start(), label, match.group("value"), match.group("unit") or ""))
    matches.sort(key=lambda item: item[0])
    if len(matches) < 2:
        return ""

    compact_matches = _compact_dimension_matches(matches)
    if len(compact_matches) < 2:
        return ""
    units = [unit for _, _, _, unit in compact_matches if unit]
    inferred_unit = units[-1] if units else ("cm" if re.search(r"\bcm\b", text, re.I) else "")
    if inferred_unit.lower() == "cm" and any(
        _is_unrealistic_centimetre_value(value) for _, _, value, _ in compact_matches
    ):
        return ""
    return _clean_text(
        " x ".join(
            f"{value}{unit or inferred_unit}{label}" for _, label, value, unit in compact_matches
        )
    )


def _compact_dimension_matches(
    matches: list[tuple[int, str, str, str]],
) -> list[tuple[int, str, str, str]]:
    compact: list[tuple[int, str, str, str]] = []
    seen: set[str] = set()
    for item in matches:
        _, label, _, _ = item
        if label in seen:
            if len(compact) >= 2:
                return compact
            compact = []
            seen = set()
        compact.append(item)
        seen.add(label)
        if len(compact) == 3:
            return compact
    return compact


def _has_dimension_signal(value: str) -> bool:
    return bool(re.search(r"(cm|in|\"|''|”|″|[WLDHPØ])", value, flags=re.IGNORECASE))


def _is_unrealistic_centimetre_value(value: str) -> bool:
    first_value = re.match(r"\s*(\d+(?:[.,]\d+)?)", value)
    if not first_value:
        return False
    return float(first_value.group(1).replace(",", ".")) >= 1000


def _extract_single_dimension(text: str) -> str:
    pattern = re.compile(
        r"\d+(?:[.,]\d+)?\s*(?:cm|in|\"|''|”|″)\s*(?:Ø|[HWDLP])\b",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        context = text[max(0, match.start() - 20) : match.end() + 20].lower()
        if re.search(r"\b(seat|back|assise|dossier)\b", context):
            continue
        return _clean_text(match.group(0))
    return ""


_SECTION_LABELS = {
    "materials",
    "materiaux",
    "dimensions",
    "features",
    "lead time",
    "condition",
    "designer",
    "maker",
    "made in",
    "provenance",
}


def _extract_labeled_section(text: str, labels: tuple[str, ...]) -> str:
    wanted_labels = {_normalize_lookup(label) for label in labels}
    section_labels = {_normalize_lookup(label) for label in _SECTION_LABELS}
    lines = [_clean_text(line) for line in (text or "").splitlines()]
    for index, line in enumerate(lines):
        if _normalize_lookup(line) not in wanted_labels:
            continue
        values = []
        for following in lines[index + 1 :]:
            normalized_following = _normalize_lookup(following)
            if not following:
                continue
            if normalized_following in section_labels:
                break
            values.append(following)
        return _clean_text(" ".join(values))
    return ""


def _extract_condition(text: str) -> str:
    lowered = text.lower()
    conditions = []
    if "restaur" in lowered or "restored" in lowered:
        conditions.append("Restored")
    if "recouvrement" in lowered or "reupholstered" in lowered:
        conditions.append("Reupholstered")
    if "refinished" in lowered:
        conditions.append("Refinished")
    return ", ".join(conditions)


def _extract_materials(text: str) -> str:
    material_keywords = [
        ("teak", ["teck", "teak"]),
        ("rosewood", ["palissandre", "rosewood"]),
        ("walnut", ["noyer", "walnut"]),
        ("glass", ["verre", "glass"]),
        ("chrome", ["chrome"]),
        ("aluminum", ["aluminium", "aluminum"]),
        ("leather", ["cuir", "leather"]),
        ("sherpa", ["sherpa"]),
        ("wood", ["bois", "wood"]),
        ("metal", ["metal", "métal"]),
    ]
    found = []
    lowered = text.lower()
    for material, keywords in material_keywords:
        if any(keyword in lowered for keyword in keywords) and material not in found:
            found.append(material)
    return ", ".join(found)


def _last_person_name(text: str) -> str:
    names = re.findall(
        r"\b[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’.-]+(?:\s+[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’.-]+)+",
        text,
    )
    return _clean_text(names[-1]) if names else ""


def _categorize_listing(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    mapping = [
        ("sideboards / credenzas", ["sideboard", "buffet", "credenza"]),
        ("dressers / commodes", ["dresser", "commode", "wardrobe"]),
        ("dining tables", ["dining table", "table a manger", "table en teck"]),
        ("dining chairs", ["dining chair", "chair", "chaises", "stool", "tabouret"]),
        ("lounge chairs", ["armchair", "fauteuil", "lounge chair"]),
        ("sofas", ["sofa", "canape"]),
        (
            "coffee tables",
            ["coffee table", "table basse", "table de salon", "tables de salon", "table d'appoint"],
        ),
        ("desks", ["desk", "bureau", "pupitre"]),
        (
            "bookshelves / wall units",
            ["bookcase", "bibliotheque", "unite murale", "wall unit", "etagere", "étagère"],
        ),
        ("nightstands", ["bedside", "chevet", "side table", "table d’appoint", "table d'appoint"]),
        ("beds / bedroom storage", ["bed", "lit"]),
        ("lighting", ["lamp", "lampe", "luminaire", "suspension"]),
    ]
    for category, keywords in mapping:
        if any(keyword in text for keyword in keywords):
            return category
    return "furniture"


def _shipping_scope_for(source: SourceDefinition) -> str:
    summary = source.shipping_summary.lower()
    if "international" in summary or "worldwide" in summary:
        return "worldwide_quote" if "quote" in summary else "international"
    if "canada" in summary and "united states" in summary:
        return "canada_us"
    if "canada" in summary:
        return "canada"
    return "local_quote"
