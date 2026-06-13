/* Pick of the Day dashboard card (plan Phase 6) — one-tap pick.
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

/* Kickoff times render in the visitor's locale (same pattern as the match
   detail page). */
document.querySelectorAll('#potd-card time[data-localize]').forEach(t => {
    const dt = new Date(t.getAttribute('datetime'));
    if (!isNaN(dt)) {
        t.textContent = dt.toLocaleString(undefined, {
            month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
        });
    }
});
