function copyFriendCode() {
    const code = document.getElementById('friend-code').textContent.trim();
    navigator.clipboard.writeText(code)
        .then(() => window.toast('Friend code copied!', {variant: 'success'}))
        .catch(() => window.toast('Could not copy code.', {variant: 'danger'}));
}

document.getElementById('regenerate-form').addEventListener('submit', function(e) {
    e.preventDefault();
    if (!confirm('Generate a new friend code? The old one will stop working.')) return;
    fetch(this.action, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': this.querySelector('[name=csrfmiddlewaretoken]').value,
        },
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            document.getElementById('friend-code').textContent = data.new_code;
            window.toast('Friend code rotated.', {variant: 'success'});
        } else {
            window.toast('Could not rotate friend code.', {variant: 'danger'});
        }
    })
    .catch(() => window.toast('Network error rotating code.', {variant: 'danger'}));
});

/* ── Filter friends list (live) ────────────────────────────────── */
function filterFriends() {
    const q = (document.getElementById('friends-filter').value || '').toLowerCase().trim();
    const items = document.getElementsByClassName('friend-item');
    let shown = 0;
    for (const item of items) {
        const name = item.dataset.name || '';
        const username = item.dataset.username || '';
        const match = !q || name.includes(q) || username.includes(q);
        item.style.display = match ? '' : 'none';
        if (match) shown += 1;
    }
    document.getElementById('friends-empty-filter').style.display = (shown === 0 && q) ? '' : 'none';
}

/* ── Invite-to-match modal ─────────────────────────────────────── */
function showInvitePopup(playerId, playerName) {
    document.getElementById('inviteMatchModal').hidden = false;
    document.getElementById('invitePlayerId').value = playerId;
    document.getElementById('confirmationText').textContent = `Invite @${playerName} to a private match?`;
}
function closeInvitePopup() {
    document.getElementById('inviteMatchModal').hidden = true;
}
function submitInviteForm() {
    const form = document.getElementById('inviteMatchForm');
    const formData = new FormData(form);
    document.getElementById('loading-overlay').hidden = false;
    closeInvitePopup();
    fetch(form.action, {
        method: 'POST',
        headers: {'X-CSRFToken': formData.get('csrfmiddlewaretoken')},
        body: formData,
    })
    .then(r => r.json().then(j => ({ ok: r.ok, body: j })))
    .then(({ ok, body }) => {
        document.getElementById('loading-overlay').hidden = true;
        if (ok && body.status === 'success') {
            window.toast('Invite sent.', {variant: 'success'});
        } else {
            // Surface server message (e.g. GoldenGameUnavailable from a future
            // accept will land in invite-list, but the create-invite endpoint
            // can also reject for other reasons — be honest about why).
            const msg = (body && body.message) || 'Could not send invite.';
            window.toast(msg, {variant: 'danger'});
        }
    })
    .catch(() => {
        document.getElementById('loading-overlay').hidden = true;
        window.toast('Network error sending invite.', {variant: 'danger'});
    });
}

/* ── Remove-friend confirm modal ───────────────────────────────── */
function confirmRemoveFriend(friendId, friendName) {
    document.getElementById('removeFriendText').textContent =
        `Remove @${friendName} from your friends list? You can re-add them via their friend code later.`;
    const btn = document.getElementById('removeFriendConfirmBtn');
    btn.onclick = () => document.getElementById('remove-form-' + friendId).submit();
    document.getElementById('removeFriendModal').hidden = false;
}
function closeRemoveModal() {
    document.getElementById('removeFriendModal').hidden = true;
}

/* ── CSP-safe event wiring (delegation) ────────────────────────── */
document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-action]');
    if (!el) return;
    const a = el.dataset.action;
    if (a === 'copy-code') copyFriendCode();
    else if (a === 'invite-open') showInvitePopup(el.dataset.friendId, el.dataset.friendUsername);
    else if (a === 'invite-close') closeInvitePopup();
    else if (a === 'invite-submit') submitInviteForm();
    else if (a === 'remove-open') confirmRemoveFriend(el.dataset.friendId, el.dataset.friendUsername);
    else if (a === 'remove-close') closeRemoveModal();
});

document.addEventListener('keyup', (e) => {
    if (e.target && e.target.id === 'friends-filter') filterFriends();
});
