from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.timezone import now
from django.contrib.auth.decorators import login_required
from core.mail.models import Notification
from core.mail.serializers.notification import NotificationSerializer
from django.views.decorators.http import require_GET, require_POST
from django.http import JsonResponse

@require_GET
@login_required(login_url='/auth/login/')
def get_notifications(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    notification_ser = NotificationSerializer(notifications, many=True)
    data = notification_ser.data

    return JsonResponse({
        'notifications': data
    })

@require_POST
@login_required(login_url='/auth/login/')
def read_notifications(request, not_id):
    try:

        Notification.objects.mark_read(not_id, request.user)


        return JsonResponse({'status': 'success'}, status=200)
    except Notification.DoesNotExist:

        return JsonResponse({'error': 'Notification not found'}, status=404)
    except Exception as e:

        return JsonResponse({'error': str(e)}, status=400)
