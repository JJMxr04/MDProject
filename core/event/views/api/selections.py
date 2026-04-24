from datetime import timedelta

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.event.models import Selection
from core.event.models.odds.quote import OddsQuote


class SelectionMovementView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, selection_id):
        selection = Selection.objects.filter(pk=selection_id).first()
        if selection is None:
            return Response({"detail": "selection not found"}, status=status.HTTP_404_NOT_FOUND)

        since_raw = request.query_params.get("since")
        since = parse_datetime(since_raw) if since_raw else None
        if since is None:
            since = timezone.now() - timedelta(hours=24)

        quotes = (
            OddsQuote.objects.filter(selection=selection, captured_at__gte=since)
            .order_by("captured_at")
            .values("decimal_odds", "captured_at")
        )
        return Response({
            "selection_id": selection.id,
            "quotes": [
                {"decimal": float(q["decimal_odds"]), "captured_at": q["captured_at"].isoformat()}
                for q in quotes
            ],
        })
