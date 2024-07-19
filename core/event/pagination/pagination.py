from core.abstract.pagination import AbstractPagination

class EventPagination(AbstractPagination):
    page_size = 50  # Set the desired page size here
    page_size_query_param = 'page_size'
    max_page_size = 100

class SportPagination(AbstractPagination):
    page_size = 150  # Set the desired page size here
    page_size_query_param = 'page_size'
    max_page_size = 150