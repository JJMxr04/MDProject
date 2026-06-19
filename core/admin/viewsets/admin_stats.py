import calendar

from django.db.models import Count, Q
from django.db.models.functions import ExtractMonth, ExtractYear
from rest_framework import status, viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from core.admin.serializers.admin_stats import AdminStatsSerializer
from core.auth.models.waitlist import WaitlistEntry
from core.user.models import User


class AdminStatsViewSet(viewsets.ViewSet):
    permission_classes = (IsAdminUser, IsAuthenticated)

    def list(self, request):
        # Get statistics for user registrations per year and month
        user_reg_stats = User.objects.annotate(
            year=ExtractYear('created'),
            month=ExtractMonth('created')
        ).values('year', 'month').annotate(
            signup_count=Count('id'),
            active_user_count=Count('id', filter=Q(is_active=True)),
        ).order_by('year', 'month')

        # Convert numeric month to month names
        for entry in user_reg_stats:
            entry['month'] = calendar.month_name[entry['month']]

        # Calculate cumulative counts for user registrations
        total_signup_count = 0
        total_active_user_count = 0
        for entry in user_reg_stats:
            total_signup_count += entry['signup_count']
            entry['signup_count'] = total_signup_count

            total_active_user_count += entry['active_user_count']
            entry['active_user_count'] = total_active_user_count

        # Get statistics for waitlist entries per year and month
        waitlist_stats = WaitlistEntry.objects.annotate(
            year=ExtractYear('created'),
            month=ExtractMonth('created')
        ).values('year', 'month').annotate(
            waitlist_count=Count('id', filter=Q(admin_granted_access=False)),
        )

        # Convert numeric month to month names
        for entry in waitlist_stats:
            entry['month'] = calendar.month_name[entry['month']]

        # Calculate total users
        total_users = User.objects.count()

        # Calculate total waitlist users that are not granted access by admin
        total_waitlist_users = WaitlistEntry.objects.filter(admin_granted_access=False).count()

        serializer = AdminStatsSerializer({
            'user_reg_stats': user_reg_stats,
            'waitlist_stats': waitlist_stats,
            'total_users': total_users,
            'total_waitlist_users': total_waitlist_users
        })

        return Response(serializer.data)
