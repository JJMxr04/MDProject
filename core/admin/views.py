from django.shortcuts import render
from django.utils import timezone
from core.auth.models.waitlist import WaitlistEntry
from core.user.models import User
from django.db.models import Count
from django.utils.dateparse import parse_date
from django.db.models.functions import ExtractMonth, ExtractDay
import calendar

def get_date_range_statistics(date_range):
    now = timezone.now()
    if date_range == 'last_7_days':
        start_date = now - timezone.timedelta(days=7)
        date_format = '%b %d'
        waitlist_entries = WaitlistEntry.objects.filter(created__gte=start_date).annotate(day=ExtractDay('created')).values('day').annotate(count=Count('id')).order_by('day')
        user_registrations = User.objects.filter(created__gte=start_date).annotate(day=ExtractDay('created')).values('day').annotate(count=Count('id')).order_by('day')
    elif date_range == 'monthly':
        start_date = now.replace(day=1)
        date_format = '%b'
        waitlist_entries = WaitlistEntry.objects.filter(created__gte=start_date).annotate(month=ExtractMonth('created')).values('month').annotate(count=Count('id')).order_by('month')
        user_registrations = User.objects.filter(created__gte=start_date).annotate(month=ExtractMonth('created')).values('month').annotate(count=Count('id')).order_by('month')
    elif date_range == 'yearly':
        start_date = now.replace(month=1, day=1)
        date_format = '%b'
        waitlist_entries = WaitlistEntry.objects.filter(created__gte=start_date).annotate(month=ExtractMonth('created')).values('month').annotate(count=Count('id')).order_by('month')
        user_registrations = User.objects.filter(created__gte=start_date).annotate(month=ExtractMonth('created')).values('month').annotate(count=Count('id')).order_by('month')
    elif date_range == 'ytd':
        start_date = now.replace(month=1, day=1)
        date_format = '%b'
        waitlist_entries = WaitlistEntry.objects.filter(created__gte=start_date).annotate(month=ExtractMonth('created')).values('month').annotate(count=Count('id')).order_by('month')
        user_registrations = User.objects.filter(created__gte=start_date).annotate(month=ExtractMonth('created')).values('month').annotate(count=Count('id')).order_by('month')
    else:  # 'all_time'
        start_date = None
        date_format = '%b'
        waitlist_entries = WaitlistEntry.objects.annotate(month=ExtractMonth('created')).values('month').annotate(count=Count('id')).order_by('month')
        user_registrations = User.objects.annotate(month=ExtractMonth('created')).values('month').annotate(count=Count('id')).order_by('month')

    if start_date:
        waitlist_signups = {i['day' if date_range == 'last_7_days' else 'month']: i['count'] for i in waitlist_entries}
        user_registrations = {i['day' if date_range == 'last_7_days' else 'month']: i['count'] for i in user_registrations}
    else:
        waitlist_signups = {i['month']: i['count'] for i in waitlist_entries}
        user_registrations = {i['month']: i['count'] for i in user_registrations}

    return waitlist_signups, user_registrations, date_format

def admin_dashboard(request):
    date_range = request.GET.get('date_range', 'last_7_days')
    chart_type = request.GET.get('chart_type', 'bar')

    waitlist_signups, user_registrations, date_format = get_date_range_statistics(date_range)

    now = timezone.now()

    if date_range == 'last_7_days':
        days = [(now - timezone.timedelta(days=i)).strftime(date_format) for i in range(6, -1, -1)]
        waitlist_data = [waitlist_signups.get((now - timezone.timedelta(days=i)).day, 0) for i in range(6, -1, -1)]
        registration_data = [user_registrations.get((now - timezone.timedelta(days=i)).day, 0) for i in range(6, -1, -1)]
    else:
        months = [calendar.month_abbr[i] for i in range(1, 13)]
        waitlist_data = [waitlist_signups.get(i, 0) for i in range(1, 13)]
        registration_data = [user_registrations.get(i, 0) for i in range(1, 13)]

    context = {
        'waitlist_signups': sum(waitlist_data if date_range == 'last_7_days' else waitlist_data),
        'user_registrations': sum(registration_data if date_range == 'last_7_days' else registration_data),
        'date_range': date_range,
        'chart_type': chart_type,
        'labels': days if date_range == 'last_7_days' else months,
        'waitlist_data': waitlist_data,
        'registration_data': registration_data,
    }
    return render(request, 'admin/dashboard/dashboard.html', context)
