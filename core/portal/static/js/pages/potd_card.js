/* Pick of the Day dashboard card — one-tap pick.
   CSP-safe delegation, same pattern as the other portal pages. */

function submitPotdPick(selectionId) {
    const card = document.getElementById('potd-card');
    if (!card) return;
    card.querySelectorAll('[data-action="potd-pick"]').forEach(b => { b.disabled = true; });
    fetch(card.dataset.pickUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': card.dataset.csrf},
        body: JSON.stringify({selection_id: selectionId}),
    })
    .then(r => r.json().then(j => ({ ok: r.ok, body: j })))
    .then(({ ok, body }) => {
        if (ok && body.status === 'success') {
            const streak = body.streak || 1;
            window.toast(`Pick locked in — ${streak}-day streak! 🔥`, {variant: 'success'});
            // Flag the celebration so it fires once on the post-reload render.
            try { sessionStorage.setItem('potd_celebrate', '1'); } catch (e) { /* private mode */ }
            setTimeout(() => window.location.reload(), 700);
        } else {
            card.querySelectorAll('[data-action="potd-pick"]').forEach(b => { b.disabled = false; });
            window.toast((body && body.message) || 'Could not save your pick.', {variant: 'danger'});
        }
    })
    .catch(() => {
        card.querySelectorAll('[data-action="potd-pick"]').forEach(b => { b.disabled = false; });
        window.toast('Network error saving your pick.', {variant: 'danger'});
    });
}

document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-action="potd-pick"]');
    if (!el) return;
    submitPotdPick(el.dataset.selectionId);
});

/* One-time post-pick celebration: the pick flow reloads the page, so fire the
   glow on the freshly-rendered locked-in card, then clear the flag. */
(function () {
    var fire;
    try { fire = sessionStorage.getItem('potd_celebrate') === '1'; } catch (e) { return; }
    if (!fire) return;
    try { sessionStorage.removeItem('potd_celebrate'); } catch (e) { /* ignore */ }
    var card = document.querySelector('.potd-hype.is-picked');
    if (card) card.classList.add('is-celebrating');
})();
