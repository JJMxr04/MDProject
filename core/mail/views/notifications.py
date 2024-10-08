from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.timezone import now
from django.contrib.auth.decorators import login_required
from core.mail.models import Notification
from core.mail.serializers.notification import NotificationSerializer
from django.views.decorators.http import require_GET,require_POST
from django.http import JsonResponse

@require_GET
@login_required(login_url='/auth/login/')
def get_notifications(request):

    # Filter tournaments based on query parameters
    notifications = Notification.objects.get_notifications(request.user)
    notification_ser = NotificationSerializer(notifications, many=True)
    data = notification_ser.data


        # Return the serialized data as a JSON response
    return JsonResponse({
        'notifications': data
    })

@require_POST
@login_required(login_url='/auth/login/')
def read_notifications(request,not_id):


    # Filter tournaments based on query parameters
    try:
        Notification.objects.mark_read(not_id)  # Fixed variable name

        # Return a 200 response
        return JsonResponse({'status': 'success'}, status=200)  # {{ edit_1 }}
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)  # {{ edit_2 }}
