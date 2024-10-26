from django.core.paginator import Paginator
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_date
from core.event.models import Event, Sport
from core.event.serializers.event import EventSerializer

@login_required(login_url='/auth/login/')
def upcoming_events_list(request):
    # Get the search query and filters
    search_query = request.GET.get('search', '')
    selected_sport = request.GET.get('sport', '')
    start_date = parse_date(request.GET.get('start_date', ''))
    end_date = parse_date(request.GET.get('end_date', ''))

    # Set up filters
    filters = {'completed': False}
    if search_query:
        filters['title__icontains'] = search_query
    if selected_sport:
        filters['sport__key'] = selected_sport
    if start_date:
        filters['commence_time__gte'] = start_date
    if end_date:
        filters['commence_time__lte'] = end_date

    # Get filtered events and apply pagination
    events = Event.objects.filter(**filters).order_by('commence_time')
    paginator = Paginator(events, 5)  # Show 5 events per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,  # Pass paginated object
        'sports': Sport.objects.all(),
        'search_query': search_query,
        'selected_sport': selected_sport,
        'start_date': start_date,
        'end_date': end_date,
    }

    return render(request, 'portal/event/upcoming-events-list.html', context)
