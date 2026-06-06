/* Create-match modal (public match list page). */
let cmMode = 'public';
let cmFriendId = null;
let cmFriendUsername = null;

document.querySelectorAll('.cm-mode__option').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.cm-mode__option').forEach(b => {
            b.classList.toggle('is-active', b === btn);
            b.setAttribute('aria-selected', b === btn ? 'true' : 'false');
        });
        cmMode = btn.dataset.mode;
        document.getElementById('cmType').value = cmMode;
        document.getElementById('cmFriendSection').hidden = (cmMode !== 'private');
        if (cmMode !== 'private') {
            cmFriendId = null; cmFriendUsername = null;
            document.querySelectorAll('.cm-friend').forEach(f => f.classList.remove('is-selected'));
        }
        updateCmPreview();
        updateCmSubmitState();
    });
});

document.querySelectorAll('.cm-friend input[type=radio]').forEach(input => {
    input.addEventListener('change', (e) => {
        cmFriendId = e.target.value;
        cmFriendUsername = e.target.dataset.username || '';
        document.querySelectorAll('.cm-friend').forEach(f => f.classList.remove('is-selected'));
        e.target.closest('.cm-friend').classList.add('is-selected');
        document.getElementById('cmPlayer').value = cmFriendId;
        updateCmPreview();
        updateCmSubmitState();
    });
});

function filterCmFriends() {
    const q = (document.getElementById('cmFriendFilter').value || '').toLowerCase().trim();
    const items = document.querySelectorAll('.cm-friend');
    let shown = 0;
    items.forEach(item => {
        const match = !q || (item.dataset.name || '').includes(q) || (item.dataset.username || '').includes(q);
        item.style.display = match ? '' : 'none';
        if (match) shown += 1;
    });
    document.getElementById('cmFriendEmpty').style.display = (shown === 0 && q) ? '' : 'none';
}

function updateCmPreview() {
    const el = document.getElementById('cmPreview');
    if (cmMode === 'public') {
        el.innerHTML = `Creating a <strong>public match</strong>. Anyone can accept and become your opponent. After acceptance, 12 slots are created with a Golden Game pre-seeded from the events catalog.`;
    } else if (cmFriendId) {
        el.innerHTML = `Inviting <strong>@${escapeHtml(cmFriendUsername || '...')}</strong> to a <strong>private match</strong>. They'll see the invite under <em>Pending invites</em> and can accept or decline.`;
    } else {
        el.innerHTML = `Pick a friend to challenge. The 12 slots and Golden Game get created when they accept your invite.`;
    }
}

function updateCmSubmitState() {
    const btn = document.getElementById('cmSubmitBtn');
    if (cmMode === 'public') {
        btn.disabled = false;
        btn.textContent = 'Create public match';
    } else {
        btn.disabled = !cmFriendId;
        btn.textContent = cmFriendId ? `Invite @${cmFriendUsername}` : 'Pick a friend';
    }
}

function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => (
        {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]
    ));
}

function submitCreateMatchForm() {
    const form = document.getElementById('createMatchForm');
    const formData = new FormData(form);
    const overlay = document.querySelector('[data-loading-overlay]');
    const modal = document.getElementById('createMatchModal');

    if (cmMode === 'private' && !cmFriendId) {
        window.toast('Pick a friend first.', {variant: 'info'});
        return;
    }

    overlay.hidden = false;
    modal.classList.remove('is-open');

    fetch(form.action, {
        method: 'POST',
        headers: {'X-CSRFToken': formData.get('csrfmiddlewaretoken')},
        body: formData,
    })
    .then(r => r.json().then(j => ({ ok: r.ok, body: j })))
    .then(({ ok, body }) => {
        overlay.hidden = true;
        if (ok && body.status === 'success') {
            if (cmMode === 'public' && body.match_id) {
                // Redirect straight to the new match's detail page so the
                // creator can see their slots immediately.
                window.location.href = `/web/portal/match/${body.match_id}/`;
                return;
            }
            window.toast(cmMode === 'public' ? 'Public match created.' : 'Invite sent.', {variant: 'success'});
            setTimeout(() => window.location.reload(), 600);
        } else {
            // Surface the server message verbatim — covers
            // GoldenGameUnavailable et al.
            const msg = (body && body.message) || 'Could not create match.';
            window.toast(msg, {variant: 'danger'});
            modal.classList.add('is-open');
        }
    })
    .catch((err) => {
        overlay.hidden = true;
        console.error(err);
        window.toast('An unexpected error occurred.', {variant: 'danger'});
        modal.classList.add('is-open');
    });
}

/* ── CSP-safe event wiring (delegation) ────────────────────────── */
document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-action]');
    if (!el) return;
    if (el.dataset.action === 'cm-submit') submitCreateMatchForm();
});

document.addEventListener('input', (e) => {
    if (e.target && e.target.id === 'cmFriendFilter') filterCmFriends();
});

// Initialize preview text on first open
updateCmPreview();
updateCmSubmitState();
