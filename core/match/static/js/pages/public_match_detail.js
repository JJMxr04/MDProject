/* Public match detail — accept-match confirmation flow.

   Moved out of the inline <script> in public_match_detail.html — the
   portal's CSP (script-src 'self') blocks inline scripts. Accept/redirect
   URLs + CSRF come from the #accept-match-config data attributes. */

const _cfg = document.getElementById('accept-match-config').dataset;

function showPopup() {
    document.getElementById('acceptMatchPopup').style.display = 'flex';
}

function closePopup() {
    document.getElementById('acceptMatchPopup').style.display = 'none';
}

function showLoading() {
    document.getElementById('loading-overlay').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loading-overlay').style.display = 'none';
}

function submitMatch() {
    showLoading(); // Show loading overlay
    closePopup(); // Close the confirmation popup

    fetch(_cfg.acceptUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': _cfg.csrf
        },
        body: JSON.stringify({
            'action': 'accept'
        })
    })
    .then(r => r.json().then(j => ({ ok: r.ok, body: j })))
    .then(({ ok, body }) => {
        if (ok && body.status === 'success') {
            window.location.href = _cfg.redirectUrl;
        } else {
            hideLoading();
            // Surface the server-side message so the user sees the
            // GoldenGameUnavailable reason ("No events scheduled...")
            // rather than a generic "Error accepting match."
            const msg = (body && body.message) || 'Error accepting match.';
            window.toast(msg, {variant: 'danger'});
            showPopup();
        }
    })
    .catch(error => {
        hideLoading();
        console.error('Error:', error);
        window.toast("An error occurred.", {variant: 'danger'});
        showPopup();
    });
}

/* ── CSP-safe event wiring (delegation) ────────────────────────────── */
document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-action]');
    if (!el) return;
    switch (el.dataset.action) {
        case 'pm-accept-open': showPopup(); break;
        case 'pm-close':       closePopup(); break;
        case 'pm-submit':      submitMatch(); break;
    }
});
