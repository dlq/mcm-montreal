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

document.addEventListener(
  "error",
  (event) => {
    const image = event.target;
    if (!(image instanceof HTMLImageElement) || !image.dataset.imageFallback) {
      return;
    }

    image.classList.add("hidden");
    const fallback = image.nextElementSibling;
    if (fallback?.classList.contains("image-fallback")) {
      fallback.classList.remove("hidden");
      fallback.classList.add("flex");
    }
  },
  true,
);
