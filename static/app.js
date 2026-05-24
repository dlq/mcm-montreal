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
    const saveForm = this.querySelector("form[data-save-search-form]");
    if (!saveForm || saveForm.dataset.ready) {
      return;
    }

    saveForm.dataset.ready = "true";
    saveForm.addEventListener("submit", () => {
      this.syncSaveForm(saveForm);
    });
  }

  syncSaveForm(saveForm) {
    const filterForm = this.querySelector("form[data-filter-form]");
    if (!filterForm) {
      return;
    }

    saveForm.querySelectorAll("input[data-synced-filter]").forEach((input) => {
      input.remove();
    });

    new FormData(filterForm).forEach((value, key) => {
      if (typeof value !== "string" || value.trim() === "") {
        return;
      }

      const input = document.createElement("input");
      input.type = "hidden";
      input.name = key;
      input.value = value;
      input.dataset.syncedFilter = "true";
      saveForm.append(input);
    });
  }
}

customElements.define("favorite-toggle", FavoriteToggle);
customElements.define("availability-pill", AvailabilityPill);
customElements.define("listing-filters", ListingFilters);

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
