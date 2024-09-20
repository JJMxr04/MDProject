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
def get_notifictions(request):

    # Filter tournaments based on query parameters
    notifications = Notification.objects.get_notifications(request.user)
    notification_ser = NotificationSerializer(notifications, many=True)
    data = notification_ser.data


        # Return the serialized data as a JSON response
    return JsonResponse({
        'notifications': data
    })

