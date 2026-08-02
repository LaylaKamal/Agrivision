(function () {
  var CROP_PAGES = {
    wheat: "crop-wheat.html",
    corn: "crop-corn.html",
    tomato: "crop-tomato.html",
    barley: "crop-barley.html",
    sorghum: "crop-sorghum.html",
  };

  var CROP_ICONS = {
    wheat: "fa-wheat-awn",
    corn: null, // custom SVG — leaf is wrong for maize
    tomato: "fa-apple-whole",
    barley: "fa-jar-wheat",
    sorghum: "fa-seedling",
  };

  function cropIconHtml(k) {
    if (k === "corn") {
      return (
        '<img class="results-ranked__crop-svg" src="images/icon-corn.svg" alt="" width="22" height="22" />'
      );
    }
    var icon = CROP_ICONS[k] || "fa-seedling";
    return '<i class="fa-solid ' + icon + '"></i>';
  }

  function cropKey(name) {
    return String(name || "").toLowerCase().trim();
  }

  function displayName(name) {
    var k = cropKey(name);
    if (!k) return name;
    return k.charAt(0).toUpperCase() + k.slice(1);
  }

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");
  }

  var wrap = document.getElementById("results-context-wrap");
  var leadEl = document.getElementById("results-context-lead");
  var grid = document.getElementById("results-context-grid");
  var listEl = document.getElementById("results-list");
  var errEl = document.getElementById("results-error");

  var raw = sessionStorage.getItem("agritech_result");
  if (!raw) {
    if (errEl) {
      errEl.hidden = false;
      errEl.textContent = "No results yet. Start from Home and choose a location.";
    }
    if (wrap) wrap.hidden = true;
    return;
  }

  var data;
  try {
    data = JSON.parse(raw);
  } catch (e) {
    if (errEl) {
      errEl.hidden = false;
      errEl.textContent = "Couldn’t load results. Please try again.";
    }
    return;
  }

  if (wrap && grid) {
    wrap.hidden = false;
    var f = (data.inputs && data.inputs.features) || {};
    var w = (data.inputs && data.inputs.weather) || {};
    var lat = data.latitude;
    var lon = data.longitude;
    if (leadEl) {
      leadEl.hidden = false;
      var savedPlace = data.place || data.city || "";
      leadEl.textContent = savedPlace
        ? "Recommendations for " + savedPlace + "."
        : "We used soil and weather at your selected point.";
    }
    grid.innerHTML =
      '<div class="context-panel">' +
      '<h3 class="context-panel__heading"><i class="fa-solid fa-location-dot"></i> Location</h3>' +
      '<dl class="context-metrics">' +
      (data.place
        ? "<div><dt>City</dt><dd>" + esc(data.place) + "</dd></div>"
        : "") +
      "<div><dt>Lat</dt><dd>" +
      esc(lat) +
      "</dd></div><div><dt>Lon</dt><dd>" +
      esc(lon) +
      "</dd></div></dl></div>" +
      '<div class="context-panel">' +
      '<h3 class="context-panel__heading"><i class="fa-solid fa-mound"></i> Soil</h3>' +
      '<dl class="context-metrics"><div><dt>pH</dt><dd>' +
      esc(f.ph) +
      "</dd></div><div><dt>Moisture</dt><dd>" +
      esc(f.soil_moisture_m3m3) +
      "</dd></div></dl></div>" +
      '<div class="context-panel">' +
      '<h3 class="context-panel__heading"><i class="fa-solid fa-cloud-sun-rain"></i> Weather</h3>' +
      '<dl class="context-metrics"><div><dt>Temp</dt><dd>' +
      esc(w.temp_c) +
      "°C</dd></div><div><dt>Rain</dt><dd>" +
      esc(w.rain_mm) +
      " mm</dd></div></dl></div>";
  }

  var rec = data.recommendations || [];
  if (!listEl) return;
  listEl.innerHTML = "";
  rec.forEach(function (row, i) {
    var k = cropKey(row.crop);
    var href = CROP_PAGES[k];
    var iconHtml = cropIconHtml(k);
    var pct = Math.round(
      Number(row.policy_adjusted_score != null ? row.policy_adjusted_score : row.match_score) || 0
    );
    var name = displayName(row.crop);
    var tip = Array.isArray(row.why) && row.why[0] ? row.why[0] : "";
    var hero = i === 0 ? " results-ranked__card--hero" : "";
    var tipHtml = tip
      ? '<span class="results-ranked__label" style="display:block;margin-top:0.25rem;opacity:0.85">' +
        esc(tip) +
        "</span>"
      : "";
    var inner =
      '<span class="results-ranked__rank">' +
      (i + 1) +
      '</span><span class="results-ranked__icon" aria-hidden="true">' +
      iconHtml +
      '</span><div class="results-ranked__meta"><span class="results-ranked__name">' +
      esc(name) +
      '</span><span class="results-ranked__label">Match</span>' +
      tipHtml +
      '</div><div class="donut donut--list donut--on-light" style="--p: ' +
      pct +
      '" aria-hidden="true"><div class="donut__ring"></div><div class="donut__hole"><span class="donut__value">' +
      pct +
      "%</span></div></div>";
    var li = document.createElement("li");
    li.innerHTML = href
      ? '<a class="results-ranked__card' + hero + '" href="' + esc(href) + '">' + inner + "</a>"
      : '<div class="results-ranked__card' + hero + '">' + inner + "</div>";
    listEl.appendChild(li);
  });
})();
