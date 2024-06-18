from django.shortcuts import render
from django.utils import timezone
from core.auth.models.waitlist import WaitlistEntry
from core.user.models import User
from django.db.models import Count
from django.utils.dateparse import parse_date
from django.db.models.functions import ExtractMonth, ExtractDay
import calendar
from django.contrib.auth.decorators import login_required

from django.shortcuts import render, redirect
from django.http import JsonResponse
from core.auth.models.waitlist import WaitlistEntry

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from core.auth.models.waitlist import WaitlistEntry
from core.admin.serializers.waitlist import WaitlistEntrySerializer

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

@login_required(login_url='/auth/login/')
def admin_dashboard(request):
    date_range = request.GET.get('date_range', 'last_7_days')
    chart_type = request.GET.get('chart_type', 'bar')

    waitlist_signups, user_registrations, date_format = get_date_range_statistics(date_range)

    now = timezone.now()

    if date_range == 'last_7_days':
        days = [(now - timezone.timedelta(days=i)).strftime(date_format) for i in range(6, -1, -1)]
        waitlist_data = [waitlist_signups.get((now - timezone.timedelta(days=i)).day, 0) for i in range(6, -1, -1)]
        registration_data = [user_registrations.get((now - timezone.timedelta(days=i)).day, 0) for i in range(6, -1, -1)]
    elif date_range == 'monthly':
        days_in_month = (now - timezone.timedelta(days=now.day)).day
        days = [str(i).zfill(2) for i in range(1, days_in_month + 1)]
        waitlist_data = [waitlist_signups.get(i, 0) for i in range(1, days_in_month + 1)]
        registration_data = [user_registrations.get(i, 0) for i in range(1, days_in_month + 1)]
    else:
        months = [calendar.month_abbr[i] for i in range(1, 13)]
        waitlist_data = [waitlist_signups.get(i, 0) for i in range(1, 13)]
        registration_data = [user_registrations.get(i, 0) for i in range(1, 13)]

    context = {
        'waitlist_signups': sum(waitlist_data),
        'user_registrations': sum(registration_data),
        'date_range': date_range,
        'chart_type': chart_type,
        'labels': days if date_range in ['last_7_days', 'monthly'] else months,
        'waitlist_data': waitlist_data,
        'registration_data': registration_data,
    }
    return render(request, 'admin/dashboard/dashboard.html', context)

@login_required(login_url='/auth/login/')
def waitlist_view(request):
    waitlist_entries = WaitlistEntry.objects.get_all_waitlist_entries()
    return render(request, 'admin/pages/waitlist.html', {'waitlist_entries': waitlist_entries})

@login_required(login_url='/auth/login/')
@require_POST
def approve_waitlist_entry(request, entry_id):
    if request.method == "POST":
        try:
            entry = WaitlistEntry.objects.approve_waitlist_entry(entry_id)
            # send_mail(
            #     'Waitlist Approval',
            #     f'Hi {entry.full_name}, your waitlist request has been approved.',
            #     'from@example.com',  # Replace with your email address
            #     [entry.email],
            #     fail_silently=False,
            # )
            return JsonResponse({'status': 'success', 'message': 'Entry approved successfully', 'full_name': entry.full_name})
        except WaitlistEntry.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Entry not found'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)
@login_required(login_url='/auth/login/')
@require_POST
def mass_approve_waitlist_entries(request):
    try:
        data = request.POST.getlist('entry_ids[]')
        if not data:
            return JsonResponse({'status': 'error', 'message': 'No entries selected'}, status=400)

        approved_entries = []
        for entry_id in data:
            try:
                entry = WaitlistEntry.objects.get(id=entry_id)
                entry.admin_granted_access = True
                entry.save()
                approved_entries.append(entry.full_name)
            except WaitlistEntry.DoesNotExist:
                continue

        return JsonResponse({'status': 'success', 'message': 'Entries approved successfully', 'approved_entries': approved_entries})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)