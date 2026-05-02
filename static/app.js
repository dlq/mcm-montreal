class FavoriteToggle extends HTMLElement {
  connectedCallback() {
    this.dataset.ready = "true";
  }
}

class AvailabilityPill extends HTMLElement {
  connectedCallback() {
    if (!this.dataset.state) {
      this.dataset.state = "unknown";
    }
  }
}

class ListingFilters extends HTMLElement {
  connectedCallback() {
    const form = this.querySelector("form");
    const summary = this.querySelector("filter-summary");
    if (!form || !summary) return;
    const fieldLabel = (key) => {
      const input = form.elements.namedItem(key);
      if (!input) return key.replaceAll("_", " ");
      if (input instanceof RadioNodeList) {
        return key.replaceAll("_", " ");
      }
      if (input.type === "checkbox") {
        return input.closest("label")?.textContent?.trim() || key.replaceAll("_", " ");
      }
      return (
        form.querySelector(`label[for="${key}"]`)?.textContent?.trim() || key.replaceAll("_", " ")
      );
    };
    const fieldValue = (key, value) => {
      const input = form.elements.namedItem(key);
      if (!input || input instanceof RadioNodeList) return String(value);
      if (input.tagName === "SELECT") {
        return input.selectedOptions[0]?.textContent?.trim() || String(value);
      }
      if (input.type === "checkbox") {
        return "";
      }
      return String(value);
    };
    const update = () => {
      const data = new FormData(form);
      const bits = [];
      for (const [key, value] of data.entries()) {
        if (!value) continue;
        if (key === "ships_to_montreal") {
          bits.push(fieldLabel(key));
          continue;
        }
        bits.push(`${fieldLabel(key)}: ${fieldValue(key, value)}`);
      }
      summary.textContent = bits.length ? bits.join(" · ") : this.dataset.defaultSummary || "";
    };
    form.addEventListener("change", update);
    form.addEventListener("input", update);
    update();
  }
}

customElements.define("favorite-toggle", FavoriteToggle);
customElements.define("availability-pill", AvailabilityPill);
customElements.define("listing-filters", ListingFilters);
