/* =========================================================
   CampusTrack — Home Page Interactions
   ========================================================= */
(function () {
  "use strict";

  var prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- Mobile nav toggle ---------- */
  var navToggle = document.getElementById("navToggle");
  var mainNav = document.getElementById("mainNav");

  if (navToggle && mainNav) {
    navToggle.addEventListener("click", function () {
      var isOpen = mainNav.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", String(isOpen));
    });

    // Close mobile menu after a link is tapped
    mainNav.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        mainNav.classList.remove("open");
        navToggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  /* ---------- Footer year ---------- */
  var yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  /* ---------- Back-to-top button ---------- */
  var toTop = document.getElementById("toTop");
  if (toTop) {
    var toggleToTop = function () {
      toTop.classList.toggle("visible", window.scrollY > 480);
    };
    window.addEventListener("scroll", toggleToTop, { passive: true });
    toggleToTop();
    toTop.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: prefersReducedMotion ? "auto" : "smooth" });
    });
  }

  /* ---------- Scroll reveal ----------
     Elements are visible by default in CSS. Only when JS runs AND
     IntersectionObserver is supported AND the user allows motion do
     we "arm" them (hide, then fade in as they enter the viewport).
     This guarantees content is never stuck invisible. */
  var revealEls = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && !prefersReducedMotion) {
    var revealObserver = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            revealObserver.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.15, rootMargin: "0px 0px -40px 0px" }
    );
    revealEls.forEach(function (el) {
      el.classList.add("reveal-armed");
      revealObserver.observe(el);
    });
  }

  /* ---------- Animated stat counters ---------- */
  function animateCount(el) {
    var target = parseInt(el.getAttribute("data-count"), 10);
    if (isNaN(target)) return;
    if (prefersReducedMotion) {
      el.textContent = target;
      return;
    }
    var start = 0;
    var duration = 900;
    var startTime = null;

    function step(timestamp) {
      if (!startTime) startTime = timestamp;
      var progress = Math.min((timestamp - startTime) / duration, 1);
      var value = Math.floor(progress * (target - start) + start);
      el.textContent = value;
      if (progress < 1) {
        window.requestAnimationFrame(step);
      } else {
        el.textContent = target;
      }
    }
    window.requestAnimationFrame(step);
  }

  var countEls = document.querySelectorAll("[data-count]");
  if ("IntersectionObserver" in window) {
    var countObserver = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            animateCount(entry.target);
            countObserver.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.6 }
    );
    countEls.forEach(function (el) { countObserver.observe(el); });
  } else {
    countEls.forEach(animateCount);
  }

  /* ---------- Bar chart animation ----------
     The SVG already ships with correct final bar heights so the chart
     is complete with no JS. When IntersectionObserver + motion are
     available we drop the bars to 0 and animate them up on scroll,
     purely as a visual flourish. */
  var barChart = document.getElementById("barChart");
  if (barChart && !prefersReducedMotion && "IntersectionObserver" in window) {
    var bars = barChart.querySelectorAll(".chart-bars rect");
    var baseline = 132; // y-axis baseline in SVG coordinate space
    var maxBarHeight = 96; // tallest bar allowed above the axis

    function renderBars() {
      bars.forEach(function (rect) {
        var pct = parseFloat(rect.getAttribute("data-h")) / 100;
        var h = Math.round(pct * maxBarHeight);
        rect.setAttribute("height", h);
        rect.setAttribute("y", baseline - h);
      });
    }
    function resetBars() {
      bars.forEach(function (rect) {
        rect.setAttribute("height", 0);
        rect.setAttribute("y", baseline);
      });
    }

    resetBars();
    var chartObserver = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            renderBars();
            chartObserver.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.4 }
    );
    chartObserver.observe(barChart);
  }
})();
