from datetime import datetime, time, timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date

from core.event.models import Event, Sport
from core.event.models.odds.market import Market


def _as_aware(d, end_of_day=False):
    if not d:
        return None
    t = time.max if end_of_day else time.min
    return timezone.make_aware(datetime.combine(d, t))


@login_required(login_url="/auth/login/")
def upcoming_events_list(request):
    search_query = request.GET.get("search", "").strip()
    selected_sport = request.GET.get("sport", "").strip()
    start_date = parse_date(request.GET.get("start_date", "") or "")
    user_end_date = parse_date(request.GET.get("end_date", "") or "")

    max_end_date = timezone.now().date() + timedelta(days=90)
    end_date = min(user_end_date, max_end_date) if user_end_date else max_end_date
    # Default floor = right now, so in-progress (live, still-bettable) events
    # stay on the list. User-supplied start_date overrides this.
    default_floor = timezone.now()

    # Show only events that have at least one Market attached — players can't
    # do anything with a bare event. Use EXISTS subquery (instead of a join +
    # distinct) so pagination row counts stay correct.
    has_markets = Market.objects.filter(event=OuterRef("pk"))

    events = (
        Event.objects
        .filter(completed=False)
        .annotate(has_markets=Exists(has_markets))
        .filter(has_markets=True)
        .select_related("home_team", "away_team", "sport")
        .order_by("start_time")
    )

    if search_query:
        # Search across team names AND season label — matches user intent.
        events = events.filter(
            Q(season_label__icontains=search_query)
            | Q(home_team__name_long__icontains=search_query)
            | Q(away_team__name_long__icontains=search_query)
        )
    if selected_sport:
        events = events.filter(sport_id=selected_sport)

    floor = _as_aware(start_date) if start_date else default_floor
    # In-progress events bypass the start-date floor (they're live now even
    # though they started in the past). Future events still need start_time
    # within the floor → end_date window.
    events = events.filter(
        Q(status_type="inprogress") | Q(start_time__gte=floor),
        start_time__lte=_as_aware(end_date, end_of_day=True),
    )

    paginator = Paginator(events, 21)
    page_obj = paginator.get_page(request.GET.get("page"))

    # Only expose sports that have at least one upcoming event WITH markets,
    # so the filter dropdown matches the list contents.
    sports = (
        Sport.objects
        .filter(events__completed=False, events__markets__isnull=False)
        .distinct()
        .order_by("name")
    )

    context = {
        "page_obj": page_obj,
        "sports": sports,
        "search_query": search_query,
        "selected_sport": selected_sport,
        "start_date": request.GET.get("start_date", ""),
        "end_date": request.GET.get("end_date", ""),
    }
    return render(request, "portal/event/upcoming-events-list.html", context)
