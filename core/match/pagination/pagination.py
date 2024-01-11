from core.abstract.pagination import AbstractPagination

class MatchPagination(AbstractPagination):
    page_size = 10  # Set the desired page size here
    page_size_query_param = 'page_size'
    max_page_size = 100