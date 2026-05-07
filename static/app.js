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

customElements.define("favorite-toggle", FavoriteToggle);
customElements.define("availability-pill", AvailabilityPill);
