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

function showImageFallback(image) {
  if (!(image instanceof HTMLImageElement) || !image.dataset.imageFallback) {
    return;
  }

  image.classList.add("hidden");
  const fallback = image.nextElementSibling;
  if (fallback?.classList.contains("image-fallback")) {
    fallback.classList.remove("hidden");
    fallback.classList.add("flex");
  }
}

function showFailedImageFallbacks(root = document) {
  root.querySelectorAll("img[data-image-fallback]").forEach((image) => {
    if (image.complete && image.naturalWidth === 0) {
      showImageFallback(image);
    }
  });
}

document.addEventListener(
  "error",
  (event) => {
    showImageFallback(event.target);
  },
  true,
);

document.addEventListener("DOMContentLoaded", () => {
  showFailedImageFallbacks();
});

document.body.addEventListener("htmx:afterSwap", (event) => {
  showFailedImageFallbacks(event.target);
});
