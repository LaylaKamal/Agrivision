(function () {
  var form = document.getElementById("location-form");
  var latEl = document.getElementById("coord-lat");
  var lonEl = document.getElementById("coord-lon");
  var gpsBtn = document.getElementById("btn-gps");
  var continueBtn = form ? form.querySelector('button[type="submit"]') : null;
  var hintEl = document.getElementById("map-hint");
  var mapGlass = document.querySelector(".map-glass--shell");
  var statusEl = document.getElementById("location-gps-status");
  var mapEl = document.getElementById("location-map");
  if (!form || !latEl || !lonEl || !statusEl || !mapEl || typeof L === "undefined") return;

  try {
    sessionStorage.removeItem("agritech_pending");
  } catch (e) {}

  var hasLocation = false;
  var fromGps = false;
  var placeName = "";
  var placeReq = 0;
  var locating = false;
  var marker = null;

  var titleEl = statusEl.querySelector(".location-gps-status__title");
  var msgEl = statusEl.querySelector(".location-gps-status__msg");
  var iconWrap = statusEl.querySelector(".location-gps-status__icon");

  var map = L.map("location-map", {
    zoomControl: true,
    attributionControl: true,
  }).setView([23.8859, 45.0792], 5);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "&copy; OpenStreetMap",
  }).addTo(map);

  setTimeout(function () {
    map.invalidateSize();
  }, 250);

  function setIcon(iconClass) {
    if (!iconWrap) return;
    iconWrap.innerHTML = '<i class="' + iconClass + '" aria-hidden="true"></i>';
  }

  function setStatus(kind, title, msg) {
    statusEl.className = "location-gps-status location-gps-status--" + kind;
    if (titleEl) titleEl.textContent = title;
    if (msgEl) msgEl.textContent = msg;
  }

  function setContinueEnabled(on) {
    if (!continueBtn) return;
    continueBtn.disabled = !on;
    continueBtn.setAttribute("aria-disabled", on ? "false" : "true");
    continueBtn.classList.toggle("is-disabled", !on);
    continueBtn.style.opacity = on ? "1" : "0.45";
    continueBtn.style.pointerEvents = on ? "" : "none";
  }

  function releaseGpsButton() {
    locating = false;
    if (!gpsBtn) return;
    gpsBtn.removeAttribute("aria-busy");
    gpsBtn.disabled = false;
  }

  function syncHint() {
    if (!hintEl) return;
    if (locating) {
      hintEl.textContent = "Detecting…";
      return;
    }
    if (!hasLocation) {
      hintEl.textContent = "Tap map or use current location";
      return;
    }
    var la = parseFloat(latEl.value);
    var lo = parseFloat(lonEl.value);
    var coords =
      Number.isFinite(la) && Number.isFinite(lo)
        ? la.toFixed(4) + ", " + lo.toFixed(4)
        : "";
    if (placeName && coords) hintEl.textContent = placeName + " · " + coords;
    else if (placeName) hintEl.textContent = placeName;
    else if (coords) hintEl.textContent = coords;
    else hintEl.textContent = "Location confirmed";
  }

  function pickPlaceName(data) {
    if (!data) return "";
    return (
      data.city ||
      data.locality ||
      data.principalSubdivision ||
      data.countryName ||
      ""
    );
  }

  function reverseGeocode(lat, lon) {
    var reqId = ++placeReq;
    fetch(
      "https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=" +
        encodeURIComponent(lat) +
        "&longitude=" +
        encodeURIComponent(lon) +
        "&localityLanguage=en"
    )
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (reqId !== placeReq) return;
        placeName = pickPlaceName(data);
        syncHint();
      })
      .catch(function () {
        if (reqId !== placeReq) return;
        placeName = "";
        syncHint();
      });
  }

  function applyCoords(lat, lon, opts) {
    opts = opts || {};
    hasLocation = true;
    fromGps = !!opts.fromGps;
    locating = false;
    latEl.value = String(lat);
    lonEl.value = String(lon);
    if (!opts.keepPlace) placeName = opts.place || "";

    if (!marker) {
      marker = L.marker([lat, lon], { draggable: true }).addTo(map);
      marker.on("dragend", function () {
        var p = marker.getLatLng();
        applyCoords(p.lat, p.lng, {
          fromGps: false,
          title: "Pin adjusted",
          msg: "Location updated. You can continue.",
        });
      });
    } else {
      marker.setLatLng([lat, lon]);
    }

    var zoom = opts.zoom != null ? opts.zoom : Math.max(map.getZoom(), 13);
    if (opts.fly !== false) map.setView([lat, lon], zoom);

    syncHint();
    setContinueEnabled(true);
    if (!opts.place) reverseGeocode(lat, lon);
    if (mapGlass) mapGlass.classList.add("map-glass--gps-active");
    setIcon("fa-solid fa-circle-check");
    setStatus(
      "success",
      opts.title || (fromGps ? "Location found" : "Location set"),
      opts.msg || "Confirm the pin, then continue."
    );
  }

  function failGps(err) {
    locating = false;
    releaseGpsButton();
    syncHint();
    var msg = "Couldn’t get GPS. Tap the map to place your pin, then continue.";
    if (err && err.code === 1) {
      msg = "Permission needed. Allow location, or tap the map to set your pin.";
    }
    setIcon("fa-solid fa-circle-info");
    setStatus("warning", "Adjust on the map", msg);
  }

  function getPosition(options) {
    return new Promise(function (resolve, reject) {
      navigator.geolocation.getCurrentPosition(resolve, reject, options);
    });
  }

  function requestFreshGps() {
    if (!navigator.geolocation) {
      failGps({ code: 2 });
      return;
    }

    locating = true;
    syncHint();
    if (gpsBtn) {
      gpsBtn.setAttribute("aria-busy", "true");
      gpsBtn.disabled = true;
    }
    setIcon("fa-solid fa-spinner fa-spin");
    setStatus(
      "loading",
      "Finding your location…",
      "Allow access when your browser asks."
    );

    getPosition({
      enableHighAccuracy: false,
      timeout: 10000,
      maximumAge: 60000,
    })
      .catch(function (err) {
        if (err && err.code === 1) throw err;
        setStatus(
          "loading",
          "Improving accuracy…",
          "Still trying GPS…"
        );
        return getPosition({
          enableHighAccuracy: true,
          timeout: 15000,
          maximumAge: 0,
        });
      })
      .then(function (pos) {
        applyCoords(pos.coords.latitude, pos.coords.longitude, {
          fromGps: true,
          zoom: 15,
          title: "Location found",
          msg: "Move the pin if needed, then continue.",
        });
        releaseGpsButton();
      })
      .catch(function (err) {
        failGps(err || { code: 3 });
      });
  }

  map.on("click", function (e) {
    applyCoords(e.latlng.lat, e.latlng.lng, {
      fromGps: false,
      fly: false,
      zoom: Math.max(map.getZoom(), 12),
      title: "Pin placed",
      msg: "Drag the pin to fine-tune, then continue.",
    });
    map.setView(e.latlng, Math.max(map.getZoom(), 12));
  });

  setIcon("fa-solid fa-location-dot");
  setStatus(
    "loading",
    "Getting your location…",
    "Allow access when asked — or tap the map."
  );
  setContinueEnabled(false);
  syncHint();

  if (gpsBtn) {
    gpsBtn.addEventListener("click", function (e) {
      e.preventDefault();
      requestFreshGps();
    });
  }

  // Try GPS as soon as the page opens
  requestFreshGps();

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var lat = parseFloat(latEl.value);
    var lon = parseFloat(lonEl.value);
    if (!hasLocation || !Number.isFinite(lat) || !Number.isFinite(lon)) {
      setIcon("fa-solid fa-circle-exclamation");
      setStatus(
        "warning",
        "Location required",
        "Use current location or tap the map first."
      );
      setContinueEnabled(false);
      return;
    }

    sessionStorage.setItem(
      "agritech_pending",
      JSON.stringify({
        lat: lat,
        lon: lon,
        place: placeName || "",
        fromGps: !!fromGps,
      })
    );
    window.location.href = "loading.html";
  });
})();
