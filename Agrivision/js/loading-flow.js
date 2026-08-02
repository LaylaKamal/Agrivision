(function () {
  var subtitle = document.querySelector(".loading-screen__subtitle");
  var note = document.querySelector(".loading-note");

  function fail(msg) {
    if (subtitle) {
      subtitle.textContent = msg;
      subtitle.classList.add("loading-screen__subtitle--error");
    }
    if (note) {
      note.innerHTML =
        '<a href="location.html">Back to location</a> · <a href="index.html">Home</a>';
    }
  }

  function setProgress(msg) {
    if (subtitle) {
      subtitle.textContent = msg;
      subtitle.classList.remove("loading-screen__subtitle--error");
    }
  }

  var raw = sessionStorage.getItem("agritech_pending");
  if (!raw) {
    fail("Please choose a location first, then try again.");
    return;
  }

  var pending;
  try {
    pending = JSON.parse(raw);
  } catch (e) {
    fail("Something went wrong. Please start again from the location step.");
    return;
  }

  if (
    !pending ||
    !Number.isFinite(Number(pending.lat)) ||
    !Number.isFinite(Number(pending.lon))
  ) {
    sessionStorage.removeItem("agritech_pending");
    fail("Location is required. Go back and set your pin on the map.");
    setTimeout(function () {
      window.location.href = "location.html";
    }, 1600);
    return;
  }

  // Ignore stale split-dev API base on the live Render site
  try {
    if (
      window.location.hostname.indexOf("onrender.com") !== -1 ||
      window.location.hostname.indexOf("trycloudflare.com") !== -1
    ) {
      localStorage.removeItem("agritech-api-base");
      if (window.AGRITECH_API) window.AGRITECH_API.baseUrl = "";
    }
  } catch (e) {}

  var base =
    window.AGRITECH_API && window.AGRITECH_API.baseUrl
      ? window.AGRITECH_API.baseUrl
      : "";

  function userFacingMessage(err) {
    var m = String((err && err.message) || "");
    if (
      m.indexOf("latitude and longitude") !== -1 ||
      m.indexOf("required numbers") !== -1
    ) {
      return "Please check your location and try again.";
    }
    if (
      m === "Failed to fetch" ||
      m === "Load failed" ||
      m.indexOf("NetworkError") !== -1 ||
      m.indexOf("network") !== -1
    ) {
      return "Unable to connect. Check your internet and try again.";
    }
    if (
      m.indexOf("not-json") !== -1 ||
      m.indexOf("not JSON") !== -1 ||
      m.indexOf("http-502") !== -1 ||
      m.indexOf("http-503") !== -1 ||
      m.indexOf("http-504") !== -1
    ) {
      return "Server is waking up. Tap Back to location and try again in a minute.";
    }
    if (m.indexOf("http-") !== -1 || m.indexOf("Request failed") !== -1) {
      return "We couldn’t complete your request. Please try again.";
    }
    return "Something went wrong. Please try again.";
  }

  function recommendOnce() {
    var url = (base ? base : "") + "/ml/recommend";
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        latitude: Number(pending.lat),
        longitude: Number(pending.lon),
        model: "blend",
        top_k: 5,
        apply_policy: true,
      }),
    }).then(function (r) {
      return r.text().then(function (text) {
        var data;
        try {
          data = text ? JSON.parse(text) : {};
        } catch (e) {
          throw new Error("not-json");
        }
        if (!r.ok) throw new Error(data.error || "http-" + r.status);
        return data;
      });
    });
  }

  function sleep(ms) {
    return new Promise(function (resolve) {
      setTimeout(resolve, ms);
    });
  }

  function recommendWithRetry() {
    var attempts = 0;
    var maxAttempts = 3;

    function next() {
      attempts += 1;
      if (attempts > 1) {
        setProgress("Waking the server… retry " + attempts + " of " + maxAttempts);
      }
      return recommendOnce().catch(function (err) {
        if (attempts >= maxAttempts) throw err;
        var m = String((err && err.message) || "");
        var retryable =
          m === "Failed to fetch" ||
          m.indexOf("not-json") !== -1 ||
          m.indexOf("http-502") !== -1 ||
          m.indexOf("http-503") !== -1 ||
          m.indexOf("http-504") !== -1 ||
          m.indexOf("NetworkError") !== -1;
        if (!retryable) throw err;
        return sleep(2500).then(next);
      });
    }

    return next();
  }

  setProgress("Analyzing soil and weather for your location…");

  recommendWithRetry()
    .then(function (data) {
      sessionStorage.setItem(
        "agritech_result",
        JSON.stringify(
          Object.assign({}, data, {
            place: pending.place || "",
          })
        )
      );
      sessionStorage.removeItem("agritech_pending");
      window.location.replace("results.html");
    })
    .catch(function (err) {
      fail(userFacingMessage(err));
    });
})();
