# import uuid
# from django.db import models
# from core.abstract.models import AbstractModel, AbstractManager
# from core.tournament.models.tournament import Tournament
# from core.match.models import Match
#
# class RoundManager(AbstractManager):
#     pass
#
# class Round(AbstractModel):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='rounds')
#     level_num = models.IntegerField()
#     next_match = models.OneToOneField(Match, related_name='next_match', on_delete=models.SET_NULL, blank=True, null=True)
#     match_1 = models.ForeignKey(Match, related_name='round_match_1', on_delete=models.SET_NULL, blank=True, null=True)
#     match_2 = models.ForeignKey(Match, related_name='round_match_2', on_delete=models.SET_NULL, blank=True, null=True)
#     next_round = models.ForeignKey('self', related_name='next_round', on_delete=models.SET_NULL, blank=True, null=True)
#     prev_round_1 = models.ForeignKey('self', related_name='prev_round_1', on_delete=models.SET_NULL, blank=True, null=True)
#     prev_round_2 = models.ForeignKey('self', related_name='prev_round_2', on_delete=models.SET_NULL, blank=True, null=True)
#     completed = models.BooleanField(default=False)
#
#     objects = RoundManager()
#
#     class Meta:
#         db_table = 'core_round'
#
#     def __str__(self):
#         return f"Round {self.level_num} of {self.tournament}"


