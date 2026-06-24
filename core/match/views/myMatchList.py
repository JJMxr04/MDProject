from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from core.match.models import Match  # Assuming you have a Match model


@login_required(login_url='/auth/login/')
def my_match_list_view(request):
    search_query = request.GET.get('search', '')
    state = request.GET.get('state', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    page = request.GET.get('page', 1)

    # Filter the matches based on search query, state, and date range


    # select_related on the FKs the list template touches (player_1,
    # player_2, winner). Without this, every row in the table drives 3
    # extra round-trips per match × 10 matches per page = 30+ queries
    # on top of the count query.
    # Duels (match_type="duel") are their own surface at /match/duels/ — keep
    # them out of the regular match list.
    matches = (
        Match.objects
        .filter(Q(player_1=request.user) | Q(player_2=request.user))
        .exclude(match_type="duel")
        .select_related("player_1", "player_2", "winner")
        .prefetch_related(
            "games__event__home_team",
            "games__event__away_team",
            "games__event__league",
        )
    )


    if search_query:
        matches = matches.filter(player_1__username__icontains=search_query) | \
                  matches.filter(player_2__username__icontains=search_query)

    if state:
        matches = matches.filter(match_state=state)

    if start_date:
        matches = matches.filter(start_date__gte=start_date)

    if end_date:
        matches = matches.filter(end_date__lte=end_date)

    matches = matches.order_by('-start_date')

    # Paginate the matches
    paginator = Paginator(matches, 10)  # Show 10 matches per page
    matches_page = paginator.get_page(page)

    # Annotate each row for the hero-style mini card (mirrors the match-detail
    # hero): viewer-relative outcome pill, both players' rank flair, and the
    # running score for each side.
    user = request.user
    from core.match.scoring import score_match
    from core.portal.cards import match_outcome, resolve_matchup_tints
    from core.ranking.standings import divisions_for, levels_for

    object_list = matches_page.object_list

    # Rank flair (phase 8): level + current-season division for BOTH players —
    # the mini now shows each side symmetrically, not just the opponent. One
    # query each for the whole page.
    player_ids = set()
    for m in object_list:
        player_ids.add(m.player_1_id)
        if m.player_2_id:
            player_ids.add(m.player_2_id)
    levels = levels_for(list(player_ids))
    divisions = divisions_for(list(player_ids))

    for match in object_list:
        match.outcome = match_outcome(match, user)
        match.p1_level = levels.get(match.player_1_id)
        match.p2_level = levels.get(match.player_2_id)
        match.p1_division = divisions.get(match.player_1_id)
        match.p2_division = divisions.get(match.player_2_id)
        # Running score for the scoreline. score_match() issues its own games
        # query, so call it once and unpack — the player_1_score/player_2_score
        # model properties would each run it again (two queries per match).
        match.p1_score, match.p2_score, _ = score_match(match)
        # Side-gradient tints, resolved the same way as the match-detail hero
        # and other matchup cards: validates the hex and falls back to the CSS
        # default blue/red when both players picked near-identical colors.
        match.home_tint, match.away_tint = resolve_matchup_tints(
            match.player_1.home_color if match.player_1 else None,
            match.player_2.away_color if match.player_2 else None,
        )

    quick_filters = [
        {"label": "All",         "value": "",          "is_active": state == ""},
        {"label": "Pending",     "value": "created",   "is_active": state == "created"},
        {"label": "In Progress", "value": "accepted",  "is_active": state == "accepted"},
        {"label": "Completed",   "value": "completed", "is_active": state == "completed"},
    ]

    context = {
        'matches': matches_page,
        'search_query': search_query,
        'state': state,
        'start_date': start_date,
        'end_date': end_date,
        'quick_filters': quick_filters,
        'total_pages': paginator.num_pages,
        'current_page': int(page)
    }

    return render(request, 'portal/match/my_match_list.html', context)
