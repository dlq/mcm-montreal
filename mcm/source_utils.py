from __future__ import annotations

import re
import unicodedata
import urllib.parse
import urllib.request
from typing import Any

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)


def _chunks(values: list[int], size: int) -> list[list[int]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _fetch_html(url: str) -> str:
    request = urllib.request.Request(_ascii_safe_url(url), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=18) as response:
        return response.read().decode("utf-8", errors="replace")


def _ascii_safe_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    netloc = parts.netloc.encode("idna").decode("ascii")
    path = urllib.parse.quote(parts.path, safe="/%:@")
    query = urllib.parse.quote(parts.query, safe="/%:@?&=+$,;")
    fragment = urllib.parse.quote(parts.fragment, safe="/%:@?&=+$,;")
    return urllib.parse.urlunsplit((parts.scheme, netloc, path, query, fragment))


def _slug_to_title(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().title()


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _safe_text(node: Any) -> str:
    if not node:
        return ""
    return _clean_text(node.get_text(" ", strip=True))


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _normalize_lookup(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.replace("'", " ").replace('"', " ")
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()


def _to_float(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = re.sub(r"[^0-9,.\s]", "", text)
    cleaned = re.sub(r"\s+", "", cleaned)
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        decimal_separator = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        cleaned = cleaned.replace(thousands_separator, "").replace(decimal_separator, ".")
    elif "," in cleaned:
        parts = cleaned.split(",")
        if len(parts[-1]) == 3 and len(parts) > 1:
            cleaned = "".join(parts)
        else:
            cleaned = "".join(parts[:-1]) + "." + parts[-1]
    elif cleaned.count(".") > 1:
        parts = cleaned.split(".")
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(cleaned)
    except ValueError:
        return None
