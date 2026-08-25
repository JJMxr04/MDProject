import calendar

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.db.models.functions import ExtractDay, ExtractMonth
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone

from core.admin.status import check_redis, get_worker_status
from core.auth import twofa
from core.auth.models.waitlist import WaitlistEntry
from core.tournament.models.tournament import Tournament
from core.user.models import User


@staff_member_required
def custom_admin_view(request):
    date_range = request.GET.get('date_range', 'last_7_days')
    chart_type = request.GET.get('chart_type', 'bar')

    waitlist_signups, user_registrations, date_format = get_date_range_statistics(date_range)

    total_users = User.objects.count()
    total_tournaments = Tournament.objects.count()

    context = {
        'waitlist_signups': sum(waitlist_signups.values()),
        'user_registrations': sum(user_registrations.values()),
        'date_range': date_range,
        'chart_type': chart_type,
        'labels': get_labels(date_range),
        'waitlist_data': get_waitlist_data(waitlist_signups, date_range),
        'registration_data': get_registration_data(user_registrations, date_range),
        'total_users': total_users,
        'total_tournaments': total_tournaments,
        'redis_status': check_redis(),
        'worker_status': get_worker_status(),
        'checked_at': timezone.localtime(),
        # Nudge staff to self-enroll in 2FA so ADMIN_REQUIRE_OTP can be flipped
        # without hand-walking each admin through the raw device model.
        'needs_2fa_setup': not twofa.has_2fa(request.user),
    }
    return TemplateResponse(request, "admin/dashboard/dashboard.html", context)

def get_date_range_statistics(date_range):
    now = timezone.now()
    if date_range == 'last_7_days':
        start_date = now - timezone.timedelta(days=7)
        date_format = '%b %d'
        waitlist_entries = WaitlistEntry.objects.filter(created__gte=start_date).annotate(day=ExtractDay('created')).values('day').annotate(count=Count('id')).order_by('day')
        user_registrations = User.objects.filter(created__gte=start_date).annotate(day=ExtractDay('created')).values('day').annotate(count=Count('id')).order_by('day')
    elif date_range == 'monthly':
        start_date = now.replace(day=1)
        date_format = '%d'
        waitlist_entries = WaitlistEntry.objects.filter(created__gte=start_date).annotate(day=ExtractDay('created')).values('day').annotate(count=Count('id')).order_by('day')
        user_registrations = User.objects.filter(created__gte=start_date).annotate(day=ExtractDay('created')).values('day').annotate(count=Count('id')).order_by('day')
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
        waitlist_signups = {i['day' if date_range in ['last_7_days', 'monthly'] else 'month']: i['count'] for i in waitlist_entries}
        user_registrations = {i['day' if date_range in ['last_7_days', 'monthly'] else 'month']: i['count'] for i in user_registrations}
    else:
        waitlist_signups = {i['month']: i['count'] for i in waitlist_entries}
        user_registrations = {i['month']: i['count'] for i in user_registrations}

    return waitlist_signups, user_registrations, date_format

def get_labels(date_range):
    now = timezone.now()
    if date_range == 'last_7_days':
        return [(now - timezone.timedelta(days=i)).strftime('%b %d') for i in range(6, -1, -1)]
    elif date_range == 'monthly':
        days_in_month = (now - timezone.timedelta(days=now.day)).day
        return [str(i).zfill(2) for i in range(1, days_in_month + 1)]
    else:
        return [calendar.month_abbr[i] for i in range(1, 13)]

def get_waitlist_data(waitlist_signups, date_range):
    now = timezone.now()
    if date_range == 'last_7_days':
        return [waitlist_signups.get((now - timezone.timedelta(days=i)).day, 0) for i in range(6, -1, -1)]
    elif date_range == 'monthly':
        days_in_month = (now - timezone.timedelta(days=now.day)).day
        return [waitlist_signups.get(i, 0) for i in range(1, days_in_month + 1)]
    else:
        return [waitlist_signups.get(i, 0) for i in range(1, 13)]

def get_registration_data(user_registrations, date_range):
    now = timezone.now()
    if date_range == 'last_7_days':
        return [user_registrations.get((now - timezone.timedelta(days=i)).day, 0) for i in range(6, -1, -1)]
    elif date_range == 'monthly':
        days_in_month = (now - timezone.timedelta(days=now.day)).day
        return [user_registrations.get(i, 0) for i in range(1, days_in_month + 1)]
    else:
        return [user_registrations.get(i, 0) for i in range(1, 13)]

class CustomAdminSite(admin.AdminSite):
    site_header = 'Custom Admin Dashboard'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_view(custom_admin_view), name='custom-dashboard'),
        ]
        return custom_urls + urls

admin_site = CustomAdminSite(name='custom_admin')
