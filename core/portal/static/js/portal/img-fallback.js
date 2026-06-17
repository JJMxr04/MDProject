// CSP-safe broken-image fallback. The portal CSP forbids inline onerror, so a
// single document-level listener in the CAPTURE phase catches <img> error
// events (which do not bubble) for the whole page — including JS-rendered
// pick-modal images, since the listener is global.
document.addEventListener("error", (e) => {
    const img = e.target;
    if (!(img instanceof HTMLImageElement)) return;
    if (img.classList.contains("team-logo")) {
        // Swap the failed <img> for the initials fallback span. The span keeps
        // .team-logo so it inherits the (tinted) background, plus the fallback
        // modifier for the initials styling.
        const span = document.createElement("span");
        span.className = "team-logo team-logo--fallback";
        span.setAttribute("aria-hidden", "true");
        span.style.cssText = img.style.cssText;            // preserve --logo-size
        span.textContent = (img.alt || "").slice(0, 2).toUpperCase();
        img.replaceWith(span);
    } else if (img.classList.contains("avatar__img")) {
        // Hide the broken avatar img; the tinted .avatar wrapper shows through.
        img.style.display = "none";
    }
}, true);
