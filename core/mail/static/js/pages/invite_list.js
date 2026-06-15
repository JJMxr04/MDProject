/* Invite list — accept / decline / cancel actions.

   Moved out of the inline <script> in invite_list.html — the portal's CSP
   (script-src 'self') blocks inline scripts. The action URL template + CSRF
   come from the #invite-list data attributes; each button carries its
   invite id + choice in data attributes.

   On success we remove the invite's row directly (instant feedback) and tidy
   up any now-empty alert/list sections, instead of relying on a full reload
   that could be skipped if a toast call threw. */

function cleanupAfterRemoval() {
    // Drop any duel "alert" section that no longer has invite rows.
    document.querySelectorAll('.duel-alert').forEach((section) => {
        if (!section.querySelector('[id^="invite-"]')) section.remove();
    });
    // If a Received/Sent list emptied out, remove its card so we don't leave a
    // dangling header behind.
    document.querySelectorAll('.list-group').forEach((list) => {
        if (!list.querySelector('[id^="invite-"]') && list.children.length === 0) {
            const card = list.closest('.card-ui');
            if (card) card.remove();
        }
    });
}

function handleInviteAction(inviteId, action) {
    const host = document.getElementById('invite-list');
    if (!host) return;
    const cfg = host.dataset;
    const overlay = document.querySelector('[data-loading-overlay]');
    if (overlay) overlay.hidden = false;

    const url = cfg.urlTemplate.replace('PLACEHOLDER', inviteId);
    fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': cfg.csrf},
        body: JSON.stringify({'action': action}),
    })
    .then(r => r.json().then(j => ({ ok: r.ok, body: j })))
    .then(({ ok, body }) => {
        if (overlay) overlay.hidden = true;
        if (ok && body.success) {
            const msgs = {accept: 'Invite accepted.', reject: 'Invite declined.', cancel: 'Invite canceled.'};
            try { if (window.toast) window.toast(msgs[action] || 'Done', {variant: 'success'}); } catch (e) {}

            const row = document.getElementById('invite-' + inviteId);
            if (row) {
                row.style.transition = 'opacity .2s ease';
                row.style.opacity = '0';
                setTimeout(() => { row.remove(); cleanupAfterRemoval(); }, 200);
            } else {
                cleanupAfterRemoval();
            }
        } else {
            const msg = (body && body.error) || 'Error processing invite. Please try again.';
            try { if (window.toast) window.toast(msg, {variant: 'danger'}); } catch (e) {}
        }
    })
    .catch((err) => {
        if (overlay) overlay.hidden = true;
        console.error(err);
        try { if (window.toast) window.toast('Error processing invite. Please try again.', {variant: 'danger'}); } catch (e) {}
    });
}

/* ── CSP-safe event wiring (delegation) ────────────────────────────── */
document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-action="invite-act"]');
    if (!el) return;
    handleInviteAction(el.dataset.inviteId, el.dataset.inviteChoice);
});
