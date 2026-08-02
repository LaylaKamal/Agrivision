(function () {
  var STORAGE_KEY = "agritech-theme";

  function getTheme() {
    try {
      return localStorage.getItem(STORAGE_KEY) === "morning" ? "morning" : "night";
    } catch (e) {
      return "night";
    }
  }

  function syncEmoji() {
    var btn = document.getElementById("theme-emoji-btn");
    if (!btn) return;
    var morning = document.documentElement.getAttribute("data-theme") === "morning";
    btn.textContent = morning ? "☀️" : "🌙";
    btn.setAttribute("aria-pressed", morning ? "true" : "false");
  }

  function apply(theme) {
    var next = theme === "morning" ? "morning" : "night";
    if (next === "morning") {
      document.documentElement.setAttribute("data-theme", "morning");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch (e) {}
    syncEmoji();
  }

  document.addEventListener("DOMContentLoaded", function () {
    apply(getTheme());

    var emojiBtn = document.getElementById("theme-emoji-btn");
    if (emojiBtn) {
      emojiBtn.addEventListener("click", function () {
        var morning = document.documentElement.getAttribute("data-theme") === "morning";
        apply(morning ? "night" : "morning");
      });
    }
  });

  window.AgriTechTheme = { apply: apply, getTheme: getTheme, syncEmoji: syncEmoji };
})();
