/* My-match detail page (pick modal, tiebreaker, game cards).

   Moved out of the inline <script> in my_match_detail.html — the portal's
   CSP (script-src 'self') blocks inline scripts. URL templates + CSRF come
   from the #match-page-config data attributes the template renders. */

/* ── URL templates ──────────────────────────────────────────────────── */
const _cfg = document.getElementById('match-page-config').dataset;
const URL_EVENT_MARKETS  = _cfg.urlEventMarkets;
const URL_EVENT_OUTCOMES = _cfg.urlEventOutcomes;
const URL_PLAYER_2_PICK  = _cfg.urlPlayer2Pick;
const URL_PICK_LOCKED    = _cfg.urlPickLocked;
const URL_UPLOAD_PICK    = _cfg.urlUploadPick;
const CSRF_TOKEN         = _cfg.csrf;

/* ── Generic loading helpers (used by tiebreaker) ───────────────────── */
function showLoading() { document.getElementById('loading-overlay').style.display = 'flex'; }
function hideLoading() { document.getElementById('loading-overlay').style.display = 'none'; }

/* ───────────────────────────────────────────────────────────────────────
 *  PICK MODAL
 *
 *  Single Bootstrap modal for both flows:
 *    • mode='upload' — clicked the page-level "Upload A Pick" button.
 *      The slot has no event yet. Show step 1 (event chooser) → step 2.
 *    • mode='game'   — clicked an existing game card on the page.
 *      The slot has an event locked to it. Skip step 1; load markets
 *      directly into step 2.
 *
 *  Selections are POSTed via the same endpoints as before.
 * ─────────────────────────────────────────────────────────────────────── */
const PickModal = (function () {
    const state = {
        mode: null,           // 'upload' | 'game'
        gameId: null,         // game uuid (always set when mode='game')
        eventId: null,        // chosen event id (set after step 1, or from server in 'game' mode)
        eventData: null,      // full event payload (used for humanized selection labels)
        markets: [],          // cached markets list for the chosen event
        activeCategory: null, // currently shown market tab
        selectedMarketId: null,
        selectedSelectionId: null,
        selectedLabel: null,
        selectedOdds: null,
        // Selections already taken on THIS game, keyed by selection_id →
        // username who took it. The picker greys these out so each player
        // must pick a different selection.
        takenSelections: {},
        // If the first player already picked a market on this game, lock
        // the second player into the SAME market — they can only pick the
        // opposite selection within it. Set on game-mode load.
        lockedMarketId: null,
        lockedMarketLabel: null,
        lockedByUsername: null,        // null when system-locked (Golden Game)
        lockedBySystem: false,         // True for Golden Game's market lock
        isCurrentUserOwner: false,     // Are we player_1 of the match?
        isGolden: false,               // Golden Game slot
    };

    let modal;
    let availableEvents = [];

    function init() {
        const el = document.getElementById('pickModal');
        modal = new bootstrap.Modal(el);
        el.addEventListener('hidden.bs.modal', resetState);

        document.getElementById('pickBackBtn').addEventListener('click', goToStep1);
        document.getElementById('pickSubmitBtn').addEventListener('click', submit);
        document.getElementById('pickEventSearch').addEventListener('input', renderEventList);

        // hydrate available events catalogue from JSON island
        try {
            const raw = document.getElementById('available-events-data');
            availableEvents = raw ? JSON.parse(raw.textContent) : [];
        } catch (e) { availableEvents = []; }
    }

    function resetState() {
        Object.assign(state, {
            mode: null, gameId: null, eventId: null, eventData: null,
            markets: [], activeCategory: null,
            selectedMarketId: null, selectedSelectionId: null,
            selectedLabel: null, selectedOdds: null,
            takenSelections: {}, opponentSelectionId: null,
            lockedMarketId: null, lockedMarketLabel: null, lockedByUsername: null,
            lockedBySystem: false, isCurrentUserOwner: false, isGolden: false,
        });
        document.getElementById('pickStep-events').hidden = true;
        document.getElementById('pickStep-selection').hidden = true;
        document.getElementById('pickBackBtn').hidden = true;
        document.getElementById('pickSelections').innerHTML =
            '<p class="text-center text-muted p-4">Loading markets…</p>';
        const gt = document.getElementById('goldenTotalField');
        if (gt) { gt.hidden = true; document.getElementById('goldenTotalInput').value = ''; }
        updatePreview();
    }

    /* Public: open the modal in 'upload' mode (no event yet). */
    function openForUpload() {
        resetState();
        state.mode = 'upload';
        document.getElementById('pickModalLabel').textContent = 'Upload a pick';
        document.getElementById('pickStep-events').hidden = false;
        renderEventList();
        modal.show();
    }

    /* Public: open the modal in 'game' mode. The slot already has an
       event linked — fetch it from the server and skip straight to step 2. */
    function openForGame(gameId) {
        resetState();
        state.mode = 'game';
        state.gameId = gameId;
        document.getElementById('pickModalLabel').textContent = 'Make a pick';
        document.getElementById('pickStep-selection').hidden = false;
        modal.show();

        const url = URL_EVENT_MARKETS.replace('00000000-0000-0000-0000-000000000000', gameId);
        fetch(url)
            .then(r => r.json())
            .then(data => {
                if (!data.event) {
                    document.getElementById('pickSelections').innerHTML =
                        '<p class="text-center text-muted p-4">No event locked to this slot yet.</p>';
                    return;
                }
                // Capture already-locked selections so the picker disables them.
                state.takenSelections = {};
                if (data.owner_outcome && data.owner_outcome.selection_id) {
                    state.takenSelections[data.owner_outcome.selection_id] =
                        data.owner_username || 'owner';
                }
                if (data.player_2_outcome && data.player_2_outcome.selection_id) {
                    state.takenSelections[data.player_2_outcome.selection_id] =
                        data.player_2_username || 'opponent';
                }
                // Zero-sum Golden Game: track which selection belongs to
                // the OPPONENT (own re-picks stay allowed).
                const oppOutcome = data.is_current_user_owner
                    ? data.player_2_outcome : data.owner_outcome;
                state.opponentSelectionId =
                    (oppOutcome && oppOutcome.selection_id) || null;
                // Lock priority:
                //   1. ``data.locked_market`` (set by the system on Golden
                //      Games — present from the moment the match is
                //      created, even before either player picks).
                //   2. owner/player_2's already-picked market (existing
                //      "first-picker locks the market" rule for regular
                //      slots).
                // Track whether the current user is the player_1 ("owner")
                // so submit() routes to the right endpoint.
                state.isCurrentUserOwner = !!data.is_current_user_owner;
                state.isGolden = !!data.is_golden;

                let lockedMarket = data.locked_market || null;
                let lockedByUsername = null;
                if (!lockedMarket) {
                    lockedMarket = data.owner_market || data.player_2_market;
                    if (lockedMarket) {
                        lockedByUsername = data.owner_market
                            ? (data.owner_username || 'owner')
                            : (data.player_2_username || 'opponent');
                    }
                }
                if (lockedMarket) {
                    state.lockedMarketId = lockedMarket.market_id;
                    state.lockedMarketLabel = humanMarketLabel(lockedMarket);
                    // For system-locked (Golden) markets there's no
                    // "by-user" attribution — the system locked it.
                    state.lockedByUsername = lockedByUsername;
                    state.lockedBySystem = !lockedByUsername && !!data.locked_market;
                }
                // Golden picks carry a mandatory total-score prediction
                // (the deep tiebreaker) — surface the input.
                const gt = document.getElementById('goldenTotalField');
                if (gt) gt.hidden = !state.lockedBySystem;
                applyEvent(data.event);
                loadMarkets(data.event.event_id);
            })
            .catch(err => {
                console.error(err);
                window.toast('Failed to load event.', { variant: 'danger' });
            });
    }

    /* ── Step 1: event chooser ─────────────────────────────────────── */
    function renderEventList() {
        const q = (document.getElementById('pickEventSearch').value || '').trim().toLowerCase();
        const filtered = availableEvents.filter(ev => {
            if (!q) return true;
            const hay = [
                ev.home_team && ev.home_team.name,
                ev.away_team && ev.away_team.name,
                ev.league && ev.league.name,
                ev.sport && ev.sport.name,
            ].filter(Boolean).join(' ').toLowerCase();
            return hay.includes(q);
        });

        const container = document.getElementById('pickEventList');
        const empty = document.getElementById('pickEventEmpty');
        document.getElementById('pickEventCount').textContent = filtered.length;

        if (!filtered.length) {
            container.innerHTML = ''; empty.hidden = false; return;
        }
        empty.hidden = true;
        container.innerHTML = filtered.map(ev => `
            <button type="button" class="pickevent-card" data-event-id="${ev.event_id}">
                <div class="pickevent-card__teams">
                    <span>${escapeHtml(ev.home_team ? ev.home_team.name : 'TBD')}</span>
                    <span class="vs">vs</span>
                    <span>${escapeHtml(ev.away_team ? ev.away_team.name : 'TBD')}</span>
                </div>
                <div class="pickevent-card__chips">
                    ${ev.sport && ev.sport.name ? `<span class="pm-chip is-sport">${escapeHtml(ev.sport.name)}</span>` : ''}
                    ${ev.league && ev.league.name ? `<span class="pm-chip is-league">${escapeHtml(ev.league.name)}</span>` : ''}
                </div>
                ${ev.start_time ? `
                <div class="pickevent-card__time">
                    <i class="bi bi-clock" aria-hidden="true"></i>
                    ${escapeHtml(formatEventTime(ev.start_time))}
                </div>` : ''}
            </button>
        `).join('');

        container.querySelectorAll('.pickevent-card').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.dataset.eventId;
                const ev = availableEvents.find(e => String(e.event_id) === String(id));
                if (!ev) return;
                applyEvent(ev);
                document.getElementById('pickStep-events').hidden = true;
                document.getElementById('pickStep-selection').hidden = false;
                document.getElementById('pickBackBtn').hidden = false; // came from step 1
                loadMarkets(ev.event_id);
            });
        });
    }

    function goToStep1() {
        if (state.mode !== 'upload') return;
        document.getElementById('pickStep-selection').hidden = true;
        document.getElementById('pickStep-events').hidden = false;
        document.getElementById('pickBackBtn').hidden = true;
        // wipe selection state but keep eventId list
        state.eventId = null; state.markets = []; state.activeCategory = null;
        state.selectedMarketId = null; state.selectedSelectionId = null;
        state.selectedLabel = null; state.selectedOdds = null;
        updatePreview();
    }

    /* ── Step 2: market + selection ────────────────────────────────── */
    function applyEvent(ev) {
        state.eventId = ev.event_id;
        const home = ev.home_team || {};
        const away = ev.away_team || {};

        document.getElementById('pickHomeTeam').textContent = home.name || 'TBD';
        document.getElementById('pickAwayTeam').textContent = away.name || 'TBD';
        document.getElementById('pickHomeLogo').innerHTML = renderTeamLogo(home);
        document.getElementById('pickAwayLogo').innerHTML = renderTeamLogo(away);

        const metaEl = document.getElementById('pickEventMeta');
        const chips = [];
        if (ev.sport && ev.sport.name) {
            chips.push(`<span class="pm-chip is-sport">${escapeHtml(ev.sport.name)}</span>`);
        }
        if (ev.league && ev.league.name) {
            chips.push(`<span class="pm-chip is-league">${escapeHtml(ev.league.name)}</span>`);
        }
        if (ev.start_time) {
            chips.push(`<span class="pm-chip"><i class="bi bi-clock me-1"></i>${escapeHtml(formatEventTime(ev.start_time))}</span>`);
        }
        // Live or finalized score badge.
        if (ev.is_live && ev.home_score != null && ev.away_score != null) {
            chips.push(`<span class="pickstep__score">
                <i class="bi bi-broadcast"></i>
                <span class="pickstep__score-num">${ev.home_score}–${ev.away_score}</span>
                LIVE
            </span>`);
        } else if (ev.is_finalized && ev.home_score != null && ev.away_score != null) {
            chips.push(`<span class="pickstep__score is-final">
                <span class="pickstep__score-num">${ev.home_score}–${ev.away_score}</span>
                FINAL
            </span>`);
        }
        metaEl.innerHTML = chips.join('');
    }

    function renderTeamLogo(team) {
        const name = (team && (team.name_short || team.name)) || '?';
        const logoUrl = team && team.logo_url;
        if (logoUrl) {
            return `<img class="team-logo" src="${escapeAttr(logoUrl)}" alt="${escapeAttr(name)}" style="--logo-size:48px;">`;
        }
        const initials = name.toString().slice(0, 2).toUpperCase();
        return `<span class="team-logo team-logo--fallback" style="--logo-size:48px;" aria-hidden="true">${escapeHtml(initials)}</span>`;
    }

    function loadMarkets(eventId) {
        const sels = document.getElementById('pickSelections');
        sels.innerHTML = '<p class="text-center text-muted p-4">Loading markets…</p>';
        document.getElementById('pickMarketTabs').innerHTML = '';

        const url = URL_EVENT_OUTCOMES.replace(/\/0\//, `/${eventId}/`);
        fetch(url)
            .then(r => r.json())
            .then(payload => {
                // Stash the event block so renderSelectionCard's
                // humanizeSelection() can read home/away team names.
                state.eventData = payload.event || null;
                const markets = (payload.event || {}).markets || [];
                state.markets = markets.filter(m => m.selections && m.selections.length);

                // If the game is locked to a specific market (because one
                // player already picked), narrow the catalogue to just that
                // market. The picker has no other options.
                if (state.lockedMarketId) {
                    const locked = state.markets.filter(m => m.market_id === state.lockedMarketId);
                    if (locked.length) {
                        state.markets = locked;
                    } else {
                        // The locked market isn't in the current odds payload
                        // (could happen if odds got refreshed and the original
                        // market disappeared). Surface a clear message.
                        sels.innerHTML = `<p class="text-center text-muted p-4">
                            ${escapeHtml(state.lockedByUsername || 'Your opponent')}
                            already picked the
                            <strong>${escapeHtml(state.lockedMarketLabel || 'market')}</strong>,
                            but it's no longer in the available odds.
                            Wait for odds to refresh or contact support.
                        </p>`;
                        return;
                    }
                }

                if (!state.markets.length) {
                    sels.innerHTML = '<p class="text-center text-muted p-4">No markets available for this event yet.</p>';
                    return;
                }
                renderMarketTabs();
                renderActiveSelections();
            })
            .catch(err => {
                console.error(err);
                sels.innerHTML = '<p class="text-center text-danger p-4">Error loading markets.</p>';
            });
    }

    function renderMarketTabs() {
        const tabs = document.getElementById('pickMarketTabs');
        const grouped = state.markets.reduce((acc, m) => {
            (acc[m.category] = acc[m.category] || []).push(m);
            return acc;
        }, {});

        // Locked-market mode: don't render tabs (no other choice). Show a
        // small inline notice instead so the user knows why.
        if (state.lockedMarketId) {
            const reason = state.lockedBySystem
                ? `the <strong>Golden Game</strong> auto-pick`
                : `${escapeHtml(state.lockedByUsername || 'your opponent')}`;
            const verb = state.lockedBySystem ? 'pre-selected' : 'picked';
            tabs.innerHTML = `
                <div class="pickmodal-locked-notice">
                    <i class="bi bi-lock-fill"></i>
                    <span>Locked to the <strong>${escapeHtml(state.lockedMarketLabel || 'market')}</strong>
                    that ${reason} ${verb}.</span>
                </div>
            `;
            state.activeCategory = Object.keys(grouped)[0];
            return;
        }

        tabs.innerHTML = Object.entries(grouped).map(([cat, ms], i) => `
            <button type="button" class="pickmarket-tab ${i === 0 ? 'is-active' : ''}"
                    data-category="${cat}">
                <span>${humanCategoryLabel(cat, ms)}</span>
                <span class="pickmarket-tab__count">${countSelections(ms)}</span>
            </button>
        `).join('');
        state.activeCategory = Object.keys(grouped)[0];

        tabs.querySelectorAll('.pickmarket-tab').forEach(btn => {
            btn.addEventListener('click', () => {
                tabs.querySelectorAll('.pickmarket-tab').forEach(t => t.classList.remove('is-active'));
                btn.classList.add('is-active');
                state.activeCategory = btn.dataset.category;
                renderActiveSelections();
            });
        });
    }

    function countSelections(markets) {
        return markets.reduce((n, m) => n + (m.selections || []).length, 0);
    }

    /* Pretty label helpers used in headers / tabs / locked-notice. */
    function humanCategoryLabel(cat, marketsInCat) {
        if (cat === 'MONEYLINE')   return 'Moneyline';
        if (cat === 'SPREAD')      return 'Spread';
        if (cat === 'TOTAL')       return 'Total';
        if (cat === 'PROPS_GAME')  return 'Game props';
        if (cat === 'PROPS_TEAM')  return 'Team props';
        return cat[0] + cat.slice(1).toLowerCase().replace(/_/g, ' ');
    }
    function humanMarketLabel(m) {
        if (!m) return '';
        let s = humanCategoryLabel(m.category, [m]);
        if (m.line != null) s += ` @ ${formatLine(m.line)}`;
        return s;
    }

    /* Header label for one market within a category group (e.g. when the
       category has multiple alt lines). */
    function marketGroupTitle(m, idx, total) {
        if (m.category === 'PROPS_GAME' || m.category === 'PROPS_TEAM') {
            const subj = m.subject_team && m.subject_team.name;
            const base = m.type ? m.type.replace(/_/g, ' ').toLowerCase() : 'Prop';
            return subj ? `${subj} — ${base}` : base.charAt(0).toUpperCase() + base.slice(1);
        }
        if (m.category === 'TOTAL')  return 'Over / Under';
        if (m.category === 'SPREAD') return 'Point spread';
        return m.type ? m.type.replace(/_/g, ' ') : `Variant ${idx + 1}`;
    }

    function renderActiveSelections() {
        const sels = document.getElementById('pickSelections');
        const inCategory = state.markets.filter(m => m.category === state.activeCategory);

        // Render every market in this category. For MONEYLINE there's usually
        // just one market with 2-3 selections; for SPREAD/TOTAL there can be
        // multiple alt lines, so add a line pill per market group.
        sels.innerHTML = inCategory.map((m, idx) => {
            const titleParts = [
                `<span class="pickmarket-group__title">${escapeHtml(marketGroupTitle(m, idx, inCategory.length))}</span>`,
            ];
            if (m.line != null) {
                titleParts.push(`<span class="pickmarket-group__line-pill">${escapeHtml(formatLine(m.line))}</span>`);
            }
            if (m.is_live) {
                titleParts.push('<span class="pm-badge is-dog">LIVE</span>');
            }
            const head = `<div class="pickmarket-group__head">${titleParts.join('')}</div>`;
            const grid = `<div class="pickstep__selections">${m.selections.map(s => {
                return renderSelectionCard(m, s);
            }).join('')}</div>`;
            return `<div class="pickmarket-group">${head}${grid}</div>`;
        }).join('');

        sels.querySelectorAll('.pickselection:not(.is-suspended)').forEach(btn => {
            btn.addEventListener('click', () => {
                // Zero-sum Golden Game: the opponent's selection is off the
                // board (server enforces too). Own re-picks stay allowed.
                if (state.lockedBySystem && state.opponentSelectionId
                        && btn.dataset.selectionId === state.opponentSelectionId) {
                    const who = state.takenSelections[btn.dataset.selectionId] || 'Your opponent';
                    window.toast(`${who} already took that side — the Golden Game is winner-take-all.`, { variant: 'info' });
                    return;
                }
                sels.querySelectorAll('.pickselection').forEach(o => o.classList.remove('is-selected'));
                btn.classList.add('is-selected');
                state.selectedMarketId    = btn.dataset.marketId;
                state.selectedSelectionId = btn.dataset.selectionId;
                state.selectedLabel       = btn.dataset.label;
                state.selectedOdds        = btn.dataset.odds;
                updatePreview();
            });
        });
    }

    /* A single selection card. Renders the humanized label (e.g. "Detroit
       Red Wings to win"), an optional line pill (for spread/total
       selections that bake the line into the selection rather than the
       market), the American odds with fav/dog color coding, and a
       sub-line with decimal + fractional + implied probability. */
    function renderSelectionCard(market, s) {
        const takenBy = state.takenSelections[s.selection_id];
        const classes = [
            'pickselection',
            s.suspended ? 'is-suspended' : '',
            takenBy ? 'is-taken' : '',
        ].filter(Boolean).join(' ');

        const odds = s.odds || null;
        const american = odds && odds.american != null ? odds.american : null;
        const decimal = odds && odds.decimal != null ? odds.decimal : null;
        const fractional = odds && odds.fractional ? odds.fractional : null;
        const oddsStr = formatAmerican(american) || (decimal != null ? String(decimal) : '—');
        const oddsClass = american == null ? '' : (american < 0 ? 'is-fav' : 'is-dog');
        const favClass = american == null ? '' : (american < 0 ? 'is-fav' : 'is-dog');
        const favLabel = american == null ? '' : (american < 0 ? 'FAV' : 'DOG');

        // Some selections embed their own line ("Over 220.5") — surface a
        // pill if the parent market has a line OR if the label looks like
        // it carries a number (e.g. "+3.5"). Keep it lightweight: only add
        // the pill if there's a meaningful number and it's not redundant
        // with the group's pill.
        const inlineLine = (s.line != null) ? formatLine(s.line) : '';
        const linePill = inlineLine
            ? `<span class="pickselection__line">${escapeHtml(inlineLine)}</span>` : '';

        const subBits = [];
        if (decimal != null) subBits.push(`Dec ${decimal}`);
        if (fractional)      subBits.push(fractional);
        const implied = (decimal != null) ? Math.round(100 / Number(decimal)) : null;

        // Settlement badge — visible after the event finalizes and the
        // aggregator's settlement webhook arrives. Hidden while PENDING so
        // pre-game cards stay clean.
        const settle = s.settlement_status;
        const settleBadge = (settle && settle !== 'PENDING')
            ? `<span class="pm-badge is-${settle.toLowerCase()}">${settle}</span>`
            : '';

        const badgeRow = takenBy
            ? `<span class="pickselection__taken">Picked by ${escapeHtml(takenBy)}</span>`
            : `<div class="pickselection__badge-row">
                ${settleBadge}
                ${favLabel ? `<span class="pm-badge ${favClass}">${favLabel}</span>` : ''}
                ${implied != null ? `<span class="pm-badge is-implied">${implied}%</span>` : ''}
                ${s.suspended ? `<span class="pm-badge is-implied">SUSPENDED</span>` : ''}
            </div>`;

        const humanLabel = humanizeSelection(state.eventData || null, market, s);

        return `
            <button type="button" class="${classes}"
                    data-market-id="${escapeAttr(market.market_id)}"
                    data-selection-id="${escapeAttr(s.selection_id)}"
                    data-label="${escapeAttr(humanLabel)}"
                    data-odds="${escapeAttr(oddsStr)}"
                    data-settle="${escapeAttr(settle || 'PENDING')}">
                    
                <div class="pickselection__row1">
                    <span class="pickselection__label">${escapeHtml(humanLabel)}</span>
                    ${linePill}
                </div>
                <div class="pickselection__odds-block">
                    <span class="pickselection__odds ${oddsClass}">${escapeHtml(oddsStr)}</span>
                    <span class="pickselection__odds-sub">${escapeHtml(subBits.join(' · '))}</span>
                </div>
                ${badgeRow}
                ${renderBooksStrip(s.by_bookmaker || [])}
            </button>
        `;
    }

    /* Render the per-book price strip inside a selection card.
       - Sorts books by best price for the bettor (highest decimal odds first).
       - Caps at 4 visible rows ("+N more" link if there are more).
       - Highlights the best price in primary text color.
       - Color-codes American by sign so favorites/underdogs read at a glance. */
    function renderBooksStrip(books) {
        const live = books.filter(b => b && b.available !== false && b.odds);
        if (!live.length) return '';
        const sorted = live.slice().sort((a, b) => {
            const da = Number((a.odds || {}).decimal || 0);
            const db = Number((b.odds || {}).decimal || 0);
            return db - da;
        });
        const VISIBLE = 4;
        const head = sorted.slice(0, VISIBLE);
        const overflow = sorted.length - head.length;
        const rows = head.map((b, i) => {
            const american = (b.odds && b.odds.american != null) ? b.odds.american : null;
            const oddsClass = american == null ? '' : (american < 0 ? 'is-fav' : 'is-dog');
            const oddsStr = formatAmerican(american) ||
                (b.odds && b.odds.decimal != null ? String(b.odds.decimal) : '—');
            const bestCls = i === 0 ? 'is-best' : '';
            const name = b.bookmaker_name || b.bookmaker_id;
            return `<div class="pickselection__book ${bestCls}">
                <span class="pickselection__book-name" title="${escapeAttr(name)}">${escapeHtml(name)}</span>
                <span class="pickselection__book-odds ${oddsClass}">${escapeHtml(oddsStr)}</span>
            </div>`;
        });
        if (overflow > 0) {
            rows.push(`<div class="pickselection__books-more">+${overflow} more</div>`);
        }
        return `<div class="pickselection__books">${rows.join('')}</div>`;
    }

    /* ── Submit / preview ──────────────────────────────────────────── */
    function updatePreview() {
        const previewEl = document.getElementById('pickPreview');
        const submitBtn = document.getElementById('pickSubmitBtn');
        if (!state.selectedSelectionId) {
            previewEl.innerHTML = '<em class="text-muted">none</em>';
            submitBtn.disabled = true;
            return;
        }
        const catLabel = state.activeCategory
            ? humanCategoryLabel(state.activeCategory, [])
            : '';
        const oddsRaw = state.selectedOdds || '';
        const isFav = oddsRaw.startsWith('-');
        const oddsClass = isFav ? 'is-fav' : 'is-dog';
        previewEl.innerHTML =
            `<strong>${escapeHtml(state.selectedLabel)}</strong>` +
            ` <span class="text-muted">· ${escapeHtml(catLabel)}</span>` +
            ` <span class="pickselection__odds ${oddsClass}" style="font-size:1rem;margin-left:.4rem">${escapeHtml(oddsRaw)}</span>`;
        submitBtn.disabled = false;
    }

    function submit() {
        if (!state.eventId || !state.selectedSelectionId) {
            window.toast('Pick a selection first.', { variant: 'info' });
            return;
        }
        const payload = {
            event_id: state.eventId,
            player_choice: state.selectedSelectionId,
        };
        if (state.lockedBySystem) {
            // Golden pick: the total-score prediction is mandatory (it's
            // the deep tiebreaker — captured here, never separately).
            const raw = (document.getElementById('goldenTotalInput').value || '').trim();
            if (raw === '' || isNaN(Number(raw)) || Number(raw) < 0) {
                window.toast('Predict the final total score to lock in your Golden Game pick.', { variant: 'info' });
                document.getElementById('goldenTotalInput').focus();
                return;
            }
            payload.tiebreaker_score = Math.round(Number(raw));
        }
        const body = JSON.stringify(payload);
        const headers = { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN };

        let url;
        if (state.mode === 'upload') {
            // Step-1-then-step-2 path (filling an empty owner-only slot).
            url = URL_UPLOAD_PICK;
        } else if (state.lockedBySystem) {
            // Golden Game: market is system-locked from the start, both
            // players use the unified locked-pick endpoint regardless of
            // owner vs player_2 side.
            url = URL_PICK_LOCKED.replace('00000000-0000-0000-0000-000000000000', state.gameId);
        } else if (state.isCurrentUserOwner) {
            // The slot's owner clicking their own card on a regular slot —
            // route to the match-level upload_pick (it'll find this slot
            // by event_id and fill owner_outcome).
            url = URL_UPLOAD_PICK;
        } else {
            // Opponent of an owned slot — set player_2_outcome.
            url = URL_PLAYER_2_PICK.replace('00000000-0000-0000-0000-000000000000', state.gameId);
        }

        document.getElementById('pickSubmitBtn').disabled = true;
        showLoading();
        fetch(url, { method: 'POST', headers, body })
            .then(r => r.json().then(j => ({ ok: r.ok, body: j })))
            .then(({ ok, body }) => {
                hideLoading();
                if (!ok) {
                    window.toast(body.message || 'Pick failed.', { variant: 'danger' });
                    document.getElementById('pickSubmitBtn').disabled = false;
                    return;
                }
                window.toast('Pick saved!', { variant: 'success' });
                modal.hide();
                setTimeout(() => window.location.reload(), 500);
            })
            .catch(err => {
                hideLoading();
                console.error(err);
                window.toast('Pick failed — network or server error.', { variant: 'danger' });
                document.getElementById('pickSubmitBtn').disabled = false;
            });
    }

    /* ── Utility ───────────────────────────────────────────────────── */
    /* Plain-English rendering of a selection. Mirror of
       core/event/odds/humanize.py — keep both sides aligned. Reads the
       aggregator's payload shape: market.category/type/scope/line/side/
       subject_team, selection.type, event.home_team.name/away_team.name. */
    function humanizeSelection(event, market, selection) {
        if (!market || !selection) return selection && (selection.label || selection.type) || '';
        const home = (event && event.home_team && event.home_team.name) || 'Home';
        const away = (event && event.away_team && event.away_team.name) || 'Away';
        const cat = market.category;
        const t = selection.type;
        const line = market.line;
        const scopeHint = scopeHintFor(market.scope);

        if (cat === 'MONEYLINE') {
            if (t === 'HOME') return `${home} to win${scopeHint}`;
            if (t === 'AWAY') return `${away} to win${scopeHint}`;
            if (t === 'DRAW') return `Draw${scopeHint}`;
            return `${t}${scopeHint}`;
        }
        if (cat === 'SPREAD') {
            const ls = line != null ? formatLine(line) : '';
            if (t === 'HOME') return `${home} ${ls}${scopeHint}`.trim();
            if (t === 'AWAY') return `${away} ${line != null ? formatLine(-line) : ''}${scopeHint}`.trim();
            return `${t} ${ls}${scopeHint}`.trim();
        }
        if (cat === 'TOTAL') {
            if (line == null) return `${titleCase(t)}${scopeHint}`;
            return `${titleCase(t)} ${line}${scopeHint}`;
        }
        if (cat === 'PROPS_TEAM') {
            const team = (market.subject_team && market.subject_team.name)
                || (market.side === 'HOME' ? home : market.side === 'AWAY' ? away : 'Team');
            const topic = topicFromMarketType(market.type);
            const linePart = line != null ? ` ${line}` : '';
            return `${team} ${topic} ${titleCase(t)}${linePart}`;
        }
        if (cat === 'PROPS_GAME') {
            if (market.type === 'SOCCER_BTTS' || market.type === 'NHL_BTTS') {
                return t === 'YES' ? 'Both teams to score: Yes' : 'Both teams to score: No';
            }
            if (market.type === 'SOCCER_DOUBLE_CHANCE') {
                if (t === '1X') return `${home} or Draw`;
                if (t === 'X2') return `${away} or Draw`;
                if (t === '12') return `${home} or ${away} (no draw)`;
            }
            if (market.type === 'SOCCER_DRAW_NO_BET') {
                if (t === 'HOME') return `${home} to win (draw refunds)`;
                if (t === 'AWAY') return `${away} to win (draw refunds)`;
            }
            return `${topicFromMarketType(market.type)}: ${titleCase(t.replace(/_/g, ' '))}`;
        }
        return selection.label || t || 'Pick';
    }

    function topicFromMarketType(mt) {
        if (!mt) return 'prop';
        const parts = mt.toLowerCase().split('_');
        const sportPrefixes = ['nfl','nhl','nba','ncaaf','ncaab','mlb','soccer','tennis','mma','ufc','uefa','champions'];
        if (parts.length && sportPrefixes.includes(parts[0])) parts.shift();
        return parts.join(' ') || 'prop';
    }
    function scopeHintFor(scope) {
        if (!scope || scope === 'FULL_GAME') return '';
        const map = {
            '1H':'1st half','2H':'2nd half',
            'Q1':'1st quarter','Q2':'2nd quarter','Q3':'3rd quarter','Q4':'4th quarter',
            '1P':'1st period','2P':'2nd period','3P':'3rd period',
        };
        return ` (${map[scope] || scope.replace(/_/g, ' ').toLowerCase()})`;
    }
    function titleCase(s) {
        return String(s || '').toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
    }

    function formatOdds(odds) {
        if (!odds) return '—';
        if (odds.american != null) return formatAmerican(odds.american);
        if (odds.decimal != null) return String(odds.decimal);
        return '—';
    }
    function formatAmerican(american) {
        if (american == null) return '';
        return (american > 0 ? '+' : '') + american;
    }
    function formatLine(line) {
        const n = Number(line);
        if (Number.isNaN(n)) return String(line);
        return (n > 0 ? '+' : '') + n;
    }
    function formatEventTime(iso) {
        try {
            const d = new Date(iso);
            return d.toLocaleString(undefined, {
                month: 'short', day: 'numeric',
                hour: 'numeric', minute: '2-digit',
            });
        } catch (e) { return String(iso); }
    }
    function escapeHtml(str) {
        return String(str ?? '').replace(/[&<>"']/g, c => (
            { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
        ));
    }
    function escapeAttr(str) { return escapeHtml(str); }

    return { init, openForUpload, openForGame };
})();

document.addEventListener('DOMContentLoaded', PickModal.init);

/* Public hooks wired via the data-action delegation below. */
function openUploadPopup()           { PickModal.openForUpload(); }
function openGamePopupById(gameId)   { PickModal.openForGame(gameId); }

/* ── Rematch (Phase 5 §5): same format, roles swapped ─────────────── */
function sendRematch(el) {
    el.disabled = true;
    fetch(el.dataset.url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': el.dataset.csrf },
        body: JSON.stringify({}),
    })
    .then(r => r.json().then(j => ({ ok: r.ok, body: j })))
    .then(({ ok, body }) => {
        if (ok && body.status === 'success') {
            window.toast(body.message || 'Rematch invite sent.', {variant: 'success'});
        } else {
            el.disabled = false;
            window.toast((body && body.message) || 'Could not send rematch.', {variant: 'danger'});
        }
    })
    .catch(() => {
        el.disabled = false;
        window.toast('Network error sending rematch.', {variant: 'danger'});
    });
}

/* ── CSP-safe event wiring (delegation) ────────────────────────────────
   Replaces the onclick= attributes the CSP (script-src-attr) blocks. */
document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-action]');
    if (!el) return;
    switch (el.dataset.action) {
        case 'open-upload':      openUploadPopup(); break;
        case 'rematch':          sendRematch(el); break;
        case 'open-game':
            // Links inside the card (e.g. "View event details") navigate;
            // replaces the old inline event.stopPropagation().
            if (e.target.closest('a')) return;
            openGamePopupById(el.dataset.gameId);
            break;
    }
});

/* Game cards render event start times in the visitor's locale — replaces
   the old inline document.write(new Date(...).toLocaleString()). */
document.querySelectorAll('time[data-localize]').forEach(t => {
    const dt = new Date(t.getAttribute('datetime'));
    if (!isNaN(dt)) t.textContent = dt.toLocaleString();
});

