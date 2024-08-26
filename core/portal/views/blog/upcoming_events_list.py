from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.event.models import Event,Sport  # Adjust import according to your project's structure
from django.utils.dateparse import parse_date

@login_required(login_url='/auth/login/')
def upcoming_events_list(request):
    # Fetch query parameters for filtering and pagination
    search_query = request.GET.get('search', '')
    selected_sport = request.GET.get('sport', '')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    page = int(request.GET.get('page', 1))

    # Prepare filters
    filters = {}
    if search_query:
        filters['title__icontains'] = search_query
    if selected_sport:
        filters['sport__key'] = selected_sport
    if start_date:
        filters['commence_time__gte'] = parse_date(start_date)
    if end_date:
        filters['commence_time__lte'] = parse_date(end_date)

    # Fetch events with filtering and pagination
    events_per_page = 10
    events = Event.objects.filter(**filters).order_by('-commence_time')
    total_events = events.count()
    events = events[(page - 1) * events_per_page: page * events_per_page]

    # Prepare pagination data
    total_pages = (total_events + events_per_page - 1) // events_per_page

    context = {
        'events': events,
        'total_pages': total_pages,
        'current_page': page,
        'sports': list(Sport.objects.all()),  # Assuming you have a Sport model
        'search_query': search_query,
        'selected_sport': selected_sport,
        'start_date': start_date,
        'end_date': end_date
    }

    return render(request, 'portal/blog/upcoming-events-list.html', context)
