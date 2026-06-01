"""Envelope-aware pagination (plan 03 — Validation, filtering, pagination).

Pagination is mandatory on every v1 collection (D11). Page-number paging,
default ``page_size=20`` (10–20 band), max 100. The paginated response is itself
an envelope (``{"data": [...], "meta": {...pagination}}``); the
``EnvelopeJSONRenderer`` then fills in ``meta.request_id`` / ``meta.generated_at``.
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class EnvelopePageNumberPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response(
            {
                "data": data,
                "meta": {
                    "page": self.page.number,
                    "page_size": self.get_page_size(self.request) or self.page_size,
                    "total": self.page.paginator.count,
                    "next": self.get_next_link(),
                    "prev": self.get_previous_link(),
                },
            }
        )
