(function () {
  var STORAGE_KEY = "agritech-api-base";

  /** Dev: UI on this port, Flask ML on :5001. */
  var SPLIT_DEV_PORTS = ["8080", "8000", "5500", "5173", "3000"];

  function trimSlash(s) {
    return String(s || "").replace(/\/+$/, "");
  }

  function apiBase() {
    try {
      var q = new URLSearchParams(window.location.search).get("api");
      if (q) {
        var base = trimSlash(q);
        try {
          localStorage.setItem(STORAGE_KEY, base);
        } catch (e) {}
        return base;
      }
    } catch (e) {}

    var port = window.location.port || "";
    var splitMode = SPLIT_DEV_PORTS.indexOf(port) !== -1;

    if (splitMode) {
      try {
        var stored = localStorage.getItem(STORAGE_KEY);
        if (stored) return trimSlash(stored);
      } catch (e) {}
      var h = window.location.hostname;
      if (h === "localhost" || h === "127.0.0.1") return trimSlash("http://127.0.0.1:5001");
      return trimSlash("http://" + h + ":5001");
    }

    // Same host as this page (production / single-port dev). Ignore stale ?api= from split dev.
    return "";
  }

  window.AGRITECH_API = { baseUrl: apiBase(), storageKey: STORAGE_KEY };
})();
