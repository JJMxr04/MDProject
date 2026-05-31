/* reveal.js — lightweight scroll-reveal + navbar scroll state.
   Progressive enhancement: if JS is off or reduced-motion is set, content is
   fully visible (see .reveal defaults / @media reduced-motion in base.css). */
(function () {
  "use strict";

  var reduce = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* --- Scroll reveal --- */
  var els = Array.prototype.slice.call(document.querySelectorAll(".reveal"));
  if (els.length) {
    if (reduce || !("IntersectionObserver" in window)) {
      els.forEach(function (el) { el.classList.add("is-visible"); });
    } else {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            io.unobserve(entry.target);
          }
        });
      }, { rootMargin: "0px 0px -10% 0px", threshold: 0.08 });
      els.forEach(function (el) { io.observe(el); });
    }
  }

  /* --- Navbar elevation on scroll --- */
  var nav = document.querySelector("[data-ps-nav]");
  if (nav) {
    var onScroll = function () {
      nav.classList.toggle("is-scrolled", window.scrollY > 8);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }
})();
