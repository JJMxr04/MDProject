from core.abstract.pagination import AbstractPagination


class GamePagination(AbstractPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100
