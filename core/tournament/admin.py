from django.contrib import admin
from django.urls import path, reverse
from django.shortcuts import render
from django.http import Http404, HttpResponseRedirect
from django.contrib import messages
from django.utils.html import format_html
from core.user.models import User
from .models.tournament import Tournament, Player, Round, InvitedPlayer
from uuid import UUID  # Import UUID for type checking

@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'state', 'max_accepted_players', 'levels', 'winner', 'final_round',
                    'view_detail_link', 'invite_players_link']

    def view_detail_link(self, obj):
        url = reverse('admin:%s_%s_custom_detail' % (self.model._meta.app_label, self.model._meta.model_name),
                      args=[obj.id])
        return format_html('<a class="button" href="{}">View Details</a>', url)

    view_detail_link.short_description = 'Detail'

    def invite_players_link(self, obj):
        url = reverse('admin:invite_players_to_tournament', args=[obj.id])
        return format_html('<a class="button" href="{}">Invite Players</a>', url)

    invite_players_link.short_description = 'Invite Players'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<path:object_id>/change/detail/', self.detail_view,
                 name='%s_%s_custom_detail' % (self.model._meta.app_label, self.model._meta.model_name)),
            path('<uuid:tournament_id>/invite-players/', self.invite_players_view, name='invite_players_to_tournament'),
        ]
        return custom_urls + urls

    def invite_players_view(self, request, tournament_id):
        try:
            tournament = self.get_object(request, tournament_id)
        except self.model.DoesNotExist:
            raise Http404("Tournament does not exist")
        if request.method == 'POST':
            player_ids = request.POST.getlist('players')
            invited_players_count = 0
            for player_id in player_ids:
                if InvitedPlayer.objects.invite_player(tournament.id, player_id):
                    invited_players_count += 1

            failed_invites_count = len(player_ids) - invited_players_count
            if failed_invites_count > 0:
                messages.error(request, f"{failed_invites_count} players failed to be invited.")
            else:
                messages.success(request, f"All players invited successfully.")

            return HttpResponseRedirect(
                reverse('admin:%s_%s_change' % (self.model._meta.app_label, self.model._meta.model_name),
                        args=[str(tournament_id)]))

        # Fetch all users to display for invitation
        users = User.objects.all()
        context = {
            'title': 'Invite Players',
            'tournament': tournament,
            'users': users,
            'opts': self.model._meta,
        }

        return render(request, 'admin/invite_players.html', context)

    invite_players_view.short_description = 'Invite Players'

    def invite_players(self, request, queryset):
        selected_tournaments = queryset.values_list('id', flat=True)
        return HttpResponseRedirect(reverse('admin:invite_players_to_tournament', args=[selected_tournaments[0]]))

    invite_players.short_description = "Invite players to selected tournaments"

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

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # Customize queryset as needed, e.g., prefetch related fields
        return queryset

    def get_list_display(self, request):
        list_display = super().get_list_display(request)
        # Add or modify list_display as needed
        return list_display

    def get_list_filter(self, request):
        list_filter = super().get_list_filter(request)
        # Add or modify list_filter as needed
        return list_filter

    def get_search_fields(self, request):
        search_fields = super().get_search_fields(request)
        # Add or modify search_fields as needed
        return search_fields

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj=obj)
        # Add or modify fieldsets as needed
        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj=obj))
        if obj:  # If editing an existing object
            readonly_fields.extend([field.name for field in obj._meta.fields if field.name not in ['name', 'start_date']])
        return readonly_fields

    def get_ordering(self, request):
        ordering = super().get_ordering(request)
        # Add or modify ordering as needed
        return ordering

    def get_actions(self, request):
        actions = super().get_actions(request)
        # Add or modify actions as needed
        return actions
@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ['tournament_name', 'player', 'seed', 'division']
    list_filter = ['tournament__name']
    search_fields = ['tournament__name', 'player__username', 'player__email']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # Customize queryset as needed, e.g., prefetch related fields
        return queryset

    def tournament_name(self, obj):
        return obj.tournament.name

    tournament_name.admin_order_field = 'tournament'  # Allows sorting by tournament name

@admin.register(InvitedPlayer)
class InvitedPlayerAdmin(admin.ModelAdmin):
    list_display = ['tournament_name', 'player', 'accepted', 'accepted_date', 'invited_date']
    list_filter = ['tournament__name', 'accepted']
    search_fields = ['tournament__name', 'player__username', 'player__email']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # Customize queryset as needed, e.g., prefetch related fields
        return queryset

    def tournament_name(self, obj):
        return obj.tournament.name

    tournament_name.admin_order_field = 'tournament'  # Allows sorting by tournament name

@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'tournament_name', 'level_num', 'match', 'next_round',
        'prev_round_1', 'prev_round_2', 'player_1', 'player_2',
        'winner', 'completed'
    ]
    list_filter = ['tournament__name', 'level_num', 'completed']
    search_fields = ['tournament__name', 'player_1__player__username', 'player_2__player__username']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related(
            'tournament', 'match', 'next_round', 'prev_round_1',
            'prev_round_2', 'player_1', 'player_2', 'winner'
        )
        return queryset

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def tournament_name(self, obj):
        return obj.tournament.name

    tournament_name.admin_order_field = 'tournament'  # Allows sorting by tournament name

