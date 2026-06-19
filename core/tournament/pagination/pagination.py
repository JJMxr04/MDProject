from core.abstract.pagination import AbstractPagination


class TournamentPagination(AbstractPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 1000

