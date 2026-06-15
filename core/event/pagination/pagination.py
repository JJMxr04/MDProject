from core.abstract.pagination import AbstractPagination

class EventPagination(AbstractPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100

class SportPagination(AbstractPagination):
    page_size = 150
    page_size_query_param = 'page_size'
    max_page_size = 150