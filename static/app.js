const SHOP_CARD_MAP_ZOOM = 12;

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

class ShopCardMap extends HTMLElement {
  connectedCallback() {
    if (this.dataset.ready) {
      return;
    }
    this.dataset.ready = "true";
    this.renderWhenLeafletIsReady();
    this.addEventListener("click", (event) => {
      if (event.target.closest("a")) {
        return;
      }
      this.openDirections();
    });
    this.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") {
        return;
      }
      event.preventDefault();
      this.openDirections();
    });
  }

  renderWhenLeafletIsReady() {
    if (window.L) {
      window.requestAnimationFrame(() => this.renderMap());
      return;
    }
    window.setTimeout(() => this.renderWhenLeafletIsReady(), 50);
  }

  renderMap() {
    const latitude = Number.parseFloat(this.dataset.latitude);
    const longitude = Number.parseFloat(this.dataset.longitude);
    const canvas = this.querySelector(".shop-card-map-canvas");
    if (
      !Number.isFinite(latitude) ||
      !Number.isFinite(longitude) ||
      !canvas ||
      canvas.dataset.ready
    ) {
      return;
    }
    canvas.dataset.ready = "true";

    const point = [latitude, longitude];
    const map = window.L.map(canvas, {
      attributionControl: true,
      boxZoom: false,
      doubleClickZoom: false,
      dragging: false,
      keyboard: false,
      scrollWheelZoom: false,
      touchZoom: false,
      zoomControl: false,
    }).setView(point, SHOP_CARD_MAP_ZOOM);

    window.L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
      maxZoom: 20,
      subdomains: "abcd",
    }).addTo(map);

    window.L.marker(point, {
      icon: window.L.divIcon({
        className: "shop-card-map-marker",
        html: "<span></span>",
        iconAnchor: [9, 9],
        iconSize: [18, 18],
      }),
      keyboard: false,
    })
      .bindTooltip(this.dataset.label || "", {
        direction: "top",
        offset: [0, -10],
        opacity: 0.95,
      })
      .addTo(map);

    const resizeMap = () => {
      map.invalidateSize({ animate: false });
      map.setView(point, SHOP_CARD_MAP_ZOOM, { animate: false });
    };
    window.requestAnimationFrame(resizeMap);
    window.setTimeout(resizeMap, 150);
    window.setTimeout(resizeMap, 500);
    new ResizeObserver(resizeMap).observe(this);
  }

  openDirections() {
    const url = this.dataset.googleUrl;
    if (url) {
      window.open(url, "_blank", "noopener,noreferrer");
    }
  }
}

customElements.define("favorite-toggle", FavoriteToggle);
customElements.define("availability-pill", AvailabilityPill);
customElements.define("listing-filters", ListingFilters);
customElements.define("shop-card-map", ShopCardMap);

const serviceWorkerAllowedHosts = new Set(["montrealmcm.ca", "www.montrealmcm.ca"]);

if ("serviceWorker" in navigator && serviceWorkerAllowedHosts.has(window.location.hostname)) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch(() => {
      // Service worker registration is an enhancement; browsing should continue normally.
    });
  });
}

if ("serviceWorker" in navigator && !serviceWorkerAllowedHosts.has(window.location.hostname)) {
  navigator.serviceWorker.getRegistrations().then((registrations) => {
    registrations.forEach((registration) => {
      registration.unregister();
    });
  });
  window.caches?.keys().then((cacheNames) => {
    cacheNames
      .filter((cacheName) => cacheName.startsWith("montreal-mcm-"))
      .forEach((cacheName) => {
        window.caches.delete(cacheName);
      });
  });
}

function shopGridColumnCount(cards) {
  const grid = cards[0]?.parentElement;
  if (!grid) {
    return 1;
  }
  return getComputedStyle(grid).gridTemplateColumns.split(" ").filter(Boolean).length || 1;
}

function groupedCardRows(cards) {
  const columnCount = shopGridColumnCount(cards);
  const rows = [];
  for (let index = 0; index < cards.length; index += columnCount) {
    rows.push({ cards: cards.slice(index, index + columnCount) });
  }
  return rows;
}

function resetShopCardAlignment(cards) {
  cards.forEach((card) => {
    card.style.removeProperty("--shop-card-intro-min");
    card.style.removeProperty("--shop-card-primary-min");
    card.style.removeProperty("--shop-card-secondary-min");
  });
}

function maxHeight(cards, selector) {
  return Math.ceil(
    cards.reduce((height, card) => {
      const items = [...card.querySelectorAll(selector)];
      const cardMax = items.reduce(
        (itemHeight, item) => Math.max(itemHeight, item.getBoundingClientRect().height),
        0,
      );
      return Math.max(height, cardMax);
    }, 0),
  );
}

function applyShopCardAlignment(cards) {
  groupedCardRows(cards).forEach(({ cards: rowCards }) => {
    const introHeight = maxHeight(rowCards, ".shop-card-intro");
    const primaryHeight = maxHeight(rowCards, ".shop-card-meta-primary");
    const secondaryHeight = maxHeight(rowCards, ".shop-card-meta-secondary");
    rowCards.forEach((card) => {
      card.style.setProperty("--shop-card-intro-min", `${introHeight}px`);
      card.style.setProperty("--shop-card-primary-min", `${primaryHeight}px`);
      card.style.setProperty("--shop-card-secondary-min", `${secondaryHeight}px`);
    });
  });
}

function refineShopCardAlignment(cards) {
  if (window.matchMedia("(max-width: 767px)").matches) {
    return;
  }
  applyShopCardAlignment(cards);
}

function alignShopCards() {
  const cards = [...document.querySelectorAll("article.shop-card")];
  resetShopCardAlignment(cards);
  if (window.matchMedia("(max-width: 767px)").matches) {
    return;
  }

  document.body.offsetHeight;
  applyShopCardAlignment(cards);
  window.requestAnimationFrame(() => {
    refineShopCardAlignment(cards);
  });
  window.setTimeout(() => refineShopCardAlignment(cards), 80);
}

let shopCardAlignmentFrame = 0;
function scheduleShopCardAlignment() {
  window.cancelAnimationFrame(shopCardAlignmentFrame);
  shopCardAlignmentFrame = window.requestAnimationFrame(alignShopCards);
}

function refreshShopCardAlignment() {
  scheduleShopCardAlignment();
  window.setTimeout(scheduleShopCardAlignment, 100);
  window.setTimeout(scheduleShopCardAlignment, 350);
  window.setTimeout(scheduleShopCardAlignment, 900);
  document.fonts?.ready.then(scheduleShopCardAlignment);
}

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
  refreshShopCardAlignment();
});

document.body.addEventListener("htmx:afterSwap", (event) => {
  showFailedImageFallbacks(event.target);
  refreshShopCardAlignment();
});

window.addEventListener("load", refreshShopCardAlignment);
window.addEventListener("resize", refreshShopCardAlignment);
