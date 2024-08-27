from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.event.models import Event, Sport  # Adjust import according to your project's structure
from django.utils.dateparse import parse_date
from django.core.paginator import Paginator

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
    paginator = Paginator(events, events_per_page)
    page_obj = paginator.get_page(page)

    context = {
        'events': page_obj.object_list,
        'total_pages': paginator.num_pages,
        'current_page': page_obj.number,
        'page_range': paginator.page_range,
        'sports': list(Sport.objects.all()),  # Assuming you have a Sport model
        'search_query': search_query,
        'selected_sport': selected_sport,
        'start_date': start_date,
        'end_date': end_date
    }

    return render(request, 'portal/blog/upcoming-events-list.html', context)
