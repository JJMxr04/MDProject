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
    http_method_names = ('post','patch')
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = MatchSerializer
    queryset = Match.objects.all()
    ordering = ['-created']
    # ordering = []
    pagination_class = MatchPagination  # Use the custom pagination class

    def get_queryset(self,state,usr):
        return Match.objects.filter(match_state=state).filter(Q(player_1=usr) | Q(player_2=usr))

    def create(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset(self.request.data['match_state'], self.request.user))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        player = request.user
        print(kwargs['pk'])
        data = request.data
        print(data)
        match = Match.objects.get_object_by_id(kwargs['pk'])
        self.check_object_permissions(self.request, match)
        # if (match.player_1 != player) or (match.player_2 != player):
        #     return Http404
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
        # return Response(serializer.data)

    # def get_object(self):
    #     print(1)
    #     print(self.kwargs['pk'])
    #     queryset = self.filter_queryset(self.get_queryset(self.kwargs['pk'], self.request.user))
    #     page = self.paginate_queryset(queryset)
    #     print(2)
    #     if page is not None:
    #         serializer = self.get_serializer(page, many=True)
    #         print(serializer.data)
    #
    #         return self.get_paginated_response(serializer.data)
    #     serializer = self.get_serializer(queryset, many=True)
    #     print(6)
    #     return Response(serializer.data)

    # def list(self, request, *args, **kwargs):
    #     queryset = self.filter_queryset(self.get_queryset(self.request.data['match_state'], self.request.user))
    #     page = self.paginate_queryset(queryset)
    #     if page is not None:
    #         serializer = self.get_serializer(page, many=True)
    #         return self.get_paginated_response(serializer.data)
    #
    #     serializer = self.get_serializer(queryset, many=True)
    #     return Response(serializer.data)







