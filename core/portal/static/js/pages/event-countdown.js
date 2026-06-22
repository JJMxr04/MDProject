/* Tipoff countdown for the upcoming-event detail hero.
 *
 * CSP-safe: no inline handlers. Reads the target time from the
 * [data-countdown-to] element's dataset (ISO 8601) and ticks the
 * [data-unit="d|h|m|s"] spans once a second until kickoff.
 */
(function () {
    "use strict";

    function pad(n) {
        return n < 10 ? "0" + n : String(n);
    }

    function start(el) {
        if (el.dataset.status && el.dataset.status !== "upcoming") {
            return;
        }
        var target = Date.parse(el.dataset.countdownTo);
        if (isNaN(target)) {
            return;
        }

        var units = {
            d: el.querySelector('[data-unit="d"]'),
            h: el.querySelector('[data-unit="h"]'),
            m: el.querySelector('[data-unit="m"]'),
            s: el.querySelector('[data-unit="s"]'),
        };

        function render() {
            var diff = target - Date.now();
            if (diff <= 0) {
                el.textContent = el.dataset.countdownDone || "Starting now";
                clearInterval(timer);
                return;
            }
            var totalSec = Math.floor(diff / 1000);
            // Under an hour → urgency styling (consumers may style .is-urgent).
            el.classList.toggle("is-urgent", totalSec < 3600);
            var days = Math.floor(totalSec / 86400);
            var hours = Math.floor((totalSec % 86400) / 3600);
            var mins = Math.floor((totalSec % 3600) / 60);
            var secs = totalSec % 60;
            if (units.d) units.d.textContent = String(days);
            if (units.h) units.h.textContent = pad(hours);
            if (units.m) units.m.textContent = pad(mins);
            if (units.s) units.s.textContent = pad(secs);
        }

        render();
        var timer = setInterval(render, 1000);
    }

    function init() {
        var nodes = document.querySelectorAll("[data-countdown-to]");
        for (var i = 0; i < nodes.length; i++) {
            start(nodes[i]);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
