from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from core.match.serializers.match import MatchSerializer
from core.match.models.match import Match
from core.match.pagination.pagination import MatchPagination
from core.abstract.viewsets import AbstractViewSet
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Q
from django.http import Http404
from core.game.models import Game
from django.db.models import Q
from django.utils import timezone
from datetime import datetime
import uuid

class MatchViewSet(AbstractViewSet):
    http_method_names = ('get','post','patch')
    authentication_classes = (JWTAuthentication,)
    filter_backends = [OrderingFilter, SearchFilter]
    permission_classes = (IsAuthenticated,)
    serializer_class = MatchSerializer
    queryset = Match.objects.all()
    ordering = ['-created']
    # ordering = []
    pagination_class = MatchPagination  # Use the custom pagination class

    def get_queryset(self):
        return Match.objects.filter(match_state="created",match_type="public")

    def get_object(self):
        obj = Match.objects.get_object_by_id(self.kwargs['pk'])

        self.check_object_permissions(self.request, obj)

        return obj

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        player_1 = request.user
        match =  Match.objects.create_match(player_1)

        serializer = self.get_serializer(match)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        player_2 = request.user
        print(kwargs['pk'])
        match = Match.objects.get_object_by_id(kwargs['pk'])
        match = Match.objects.accept_match(match, player_2)
        serializer = self.get_serializer(match)
        return Response(serializer.data)



class MyMatchViewSet(AbstractViewSet):
    http_method_names = ('get', 'post', 'patch')
    authentication_classes = (JWTAuthentication,)
    filter_backends = [OrderingFilter, SearchFilter]
    permission_classes = (IsAuthenticated,)
    serializer_class = MatchSerializer
    queryset = Match.objects.all()
    ordering = ['-created']
    pagination_class = MatchPagination  # Use the custom pagination class
    search_fields = ['player_1__username', 'player_2__username', 'match_state', 'match_type']  # Add more fields if needed

    def get_queryset(self):
        user = self.request.user
        queryset = Match.objects.filter(
            Q(player_1=user) | Q(player_2=user)
        ).distinct()

        allowed_params = ['match_state', 'search', 'start_date_start', 'start_date_end']  # Define the allowed parameters
        filter_kwargs = {}

        for param in allowed_params:
            value = self.request.query_params.get(param, None)
            if value:
                if param == 'search':
                    queryset = queryset.filter(
                        Q(player_1__username__icontains=value) |
                        Q(player_2__username__icontains=value) |
                        Q(match_state__icontains=value) |
                        Q(match_type__icontains=value)
                    )
                elif param == 'start_date_start':
                    try:
                        start_date = datetime.strptime(value, '%Y-%m-%d')
                        start_date = timezone.make_aware(start_date, timezone.get_current_timezone())
                        filter_kwargs['start_date__gte'] = start_date
                    except ValueError:
                        pass  # Handle the error or log it
                elif param == 'start_date_end':
                    try:
                        end_date = datetime.strptime(value, '%Y-%m-%d')
                        end_date = timezone.make_aware(end_date, timezone.get_current_timezone())
                        filter_kwargs['start_date__lte'] = end_date
                    except ValueError:
                        pass  # Handle the error or log it
                elif param == 'match_state':
                    filter_kwargs['match_state'] = value

        queryset = queryset.filter(**filter_kwargs)
        return queryset

    def get_object(self):
        obj = Match.objects.get(pk=self.kwargs['pk'])
        self.check_object_permissions(self.request, obj)
        return obj

    def list(self, request, *args, **kwargs):
        if 'user' in request.path:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        player_1 = request.user
        match = Match.objects.create_match(player_1)
        serializer = self.get_serializer(match)
        return Response(serializer.data)


#     http_method_names = ('post','patch')
#     authentication_classes = (JWTAuthentication,)
#     permission_classes = (IsAuthenticated,)
#     serializer_class = MatchSerializer
#     queryset = Match.objects.all()
#     ordering = ['-created']
#     # ordering = []
#     pagination_class = MatchPagination  # Use the custom pagination class
#
#     def get_queryset(self,state,usr):
#         return Match.objects.filter(match_state=state).filter(Q(player_1=usr) | Q(player_2=usr))
#
#     def create(self, request, *args, **kwargs):
#         queryset = self.filter_queryset(self.get_queryset(self.request.data['match_state'], self.request.user))
#         page = self.paginate_queryset(queryset)
#         if page is not None:
#             serializer = self.get_serializer(page, many=True)
#             return self.get_paginated_response(serializer.data)
#
#         serializer = self.get_serializer(queryset, many=True)
#         return Response(serializer.data)
#
    def update(self, request, *args, **kwargs):
        player = request.user
        data = request.data
        match = Match.objects.get_object_by_id(kwargs['pk'])
        self.check_object_permissions(self.request, match)
        print("permissions")
        eventList = []

        if match.golden_game.event !=None:
            eventList.append(match.golden_game.event.id)
        if match.player_1_game_1.event !=None:
            eventList.append(match.player_1_game_1.event.id)
        if match.player_1_game_2.event !=None:
            eventList.append(match.player_1_game_2.event.id)
        if match.player_1_game_3.event !=None:
            eventList.append(match.player_1_game_3.event.id)
        if match.player_1_game_4.event !=None:
            eventList.append(match.player_1_game_4.event.id)
        if match.player_1_game_5.event !=None:
            eventList.append(match.player_1_game_5.event.id)
        if match.player_2_game_1.event !=None:
            eventList.append(match.player_2_game_1.event.id)
        if match.player_2_game_2.event !=None:
            eventList.append(match.player_2_game_2.event.id)
        if match.player_2_game_3.event !=None:
            eventList.append(match.player_2_game_3.event.id)
        if match.player_2_game_4.event !=None:
            eventList.append(match.player_2_game_4.event.id)
        if match.player_2_game_5.event !=None:
            eventList.append(match.player_2_game_5.event.id)
        if uuid.UUID(data.get("event_id")) in eventList:
            return Response(
                {'error': "This game is already been selected"},
                status=400)
        if (match.player_1 != player) and (match.player_2 != player):
            return Response({'error': "Either you are not a participant of this match or You already uploaded your games"}, status=400)
        if match.player_1 == player:
            if match.player_1_game_1.event == None:
                Game.objects.update_by_id(match.player_1_game_1.id,player,data)
                return Response({'message': 'Request was successful'}, status=200)
            if match.player_1_game_2.event == None:
                Game.objects.update_by_id(match.player_1_game_2.id, player, data)
                return Response({'message': 'Request was successful'}, status=200)
            if match.player_1_game_3.event == None:
                Game.objects.update_by_id(match.player_1_game_3.id,player,data)
                return Response({'message': 'Request was successful'}, status=200)
            if match.player_1_game_4.event == None:
                Game.objects.update_by_id(match.player_1_game_4.id, player, data)
                return Response({'message': 'Request was successful'}, status=200)
            if match.player_1_game_5.event == None:
                Game.objects.update_by_id(match.player_1_game_5.id, player, data)
                return Response({'message': 'Request was successful'}, status=200)
        if match.player_2 == player:
            if match.player_2_game_1.event == None:
                Game.objects.update_by_id(match.player_2_game_1.id,player,data)
                return Response({'message': 'Request was successful'}, status=200)
            if match.player_2_game_2.event == None:
                Game.objects.update_by_id(match.player_2_game_2.id, player, data)
                return Response({'message': 'Request was successful'}, status=200)
            if match.player_2_game_3.event == None:
                Game.objects.update_by_id(match.player_2_game_3.id,player,data)
                return Response({'message': 'Request was successful'}, status=200)
            if match.player_2_game_4.event == None:
                Game.objects.update_by_id(match.player_2_game_4.id, player, data)
                return Response({'message': 'Request was successful'}, status=200)
            if match.player_2_game_5.event == None:
                Game.objects.update_by_id(match.player_2_game_5.id, player, data)
                return Response({'message': 'Request was successful'}, status=200)

        return Response({'error': "Either you are not a participant of this match or You already uploaded your games"}, status=400)
