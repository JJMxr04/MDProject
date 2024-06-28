from django.contrib import admin
from django.urls import path, reverse
from django.shortcuts import render
from django.http import Http404
from .models.tournament import Tournament, Player, Round, InvitedPlayer
from django.utils.html import format_html

@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'view_detail_link']

    def view_detail_link(self, obj):
        url = reverse('admin:%s_%s_custom_detail' % (self.model._meta.app_label, self.model._meta.model_name),
                      args=[obj.id])
        return format_html('<a class="button" href="{}">View Details</a>', url)

    view_detail_link.short_description = 'Detail'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<path:object_id>/change/detail/', self.detail_view,
                 name='%s_%s_custom_detail' % (self.model._meta.app_label, self.model._meta.model_name)),
        ]
        return custom_urls + urls

    def detail_view(self, request, object_id):
        try:
            tournament = self.get_object(request, object_id)
        except self.model.DoesNotExist:
            raise Http404("Tournament does not exist")

        # Fetch tournament details with associated rounds using TournamentManager method
        tournament_with_rounds = Tournament.objects.get_tournament_with_rounds(object_id)

        context = {
            'tournament': tournament_with_rounds,
            'opts': self.model._meta,  # Add this line to ensure breadcrumbs are rendered
            'original': tournament,    # Add this line to ensure breadcrumbs are rendered
        }

        return render(request, 'admin/tournament_detail.html', context)


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ['tournament_name', 'player', 'seed', 'division']
    list_filter = ['tournament__name']
    search_fields = ['tournament__name', 'player__username', 'player__email']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tournament', 'player')

    def tournament_name(self, obj):
        return obj.tournament.name

    tournament_name.admin_order_field = 'tournament'  # Allows sorting by tournament name

@admin.register(InvitedPlayer)
class InvitedPlayerAdmin(admin.ModelAdmin):
    list_display = ['tournament_name', 'player', 'accepted', 'accepted_date', 'invited_date']
    list_filter = ['tournament__name', 'accepted']
    search_fields = ['tournament__name', 'player__username', 'player__email']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tournament', 'player')

    def tournament_name(self, obj):
        return obj.tournament.name

    tournament_name.admin_order_field = 'tournament'  # Allows sorting by tournament name


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ['tournament_name', 'level_num', 'player_1', 'player_2', 'winner', 'completed']
    list_filter = ['tournament__name', 'level_num', 'completed']
    search_fields = ['tournament__name', 'player_1__player__username', 'player_2__player__username']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tournament', 'player_1__player', 'player_2__player', 'winner')

    def tournament_name(self, obj):
        return obj.tournament.name

    tournament_name.admin_order_field = 'tournament'  # Allows sorting by tournament name
