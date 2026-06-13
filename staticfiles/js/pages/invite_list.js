/* Invite list — accept / decline actions.

   Moved out of the inline <script> in invite_list.html — the portal's CSP
   (script-src 'self') blocks inline scripts. The action URL template + CSRF
   come from the #invite-list data attributes; each button carries its
   invite id + choice in data attributes. */

function handleInviteAction(inviteId, action) {
    const cfg = document.getElementById('invite-list').dataset;
    const overlay = document.querySelector('[data-loading-overlay]');
    overlay.hidden = false;
    const url = cfg.urlTemplate.replace('PLACEHOLDER', inviteId);
    fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': cfg.csrf},
        body: JSON.stringify({'action': action}),
    })
    .then(r => r.json().then(j => ({ ok: r.ok, body: j })))
    .then(({ ok, body }) => {
        overlay.hidden = true;
        if (ok && body.success) {
            const msgs = {accept: 'Invite accepted.', reject: 'Invite declined.', cancel: 'Invite canceled.'};
            window.toast(msgs[action] || body.success, {variant: 'success'});
            setTimeout(() => window.location.reload(), 600);
        } else {
            // Surface the server-side message so users see "No events are
            // scheduled for your match window..." instead of a generic banner.
            const msg = (body && body.error) || 'Error processing invite. Please try again.';
            window.toast(msg, {variant: 'danger'});
        }
    })
    .catch((err) => {
        overlay.hidden = true;
        console.error(err);
        window.toast('Error processing invite. Please try again.', {variant: 'danger'});
    });
}

/* ── CSP-safe event wiring (delegation) ────────────────────────────── */
document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-action="invite-act"]');
    if (!el) return;
    handleInviteAction(el.dataset.inviteId, el.dataset.inviteChoice);
});
