import uuid
from decimal import Decimal

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from core.api.auth import V1_AUTHENTICATION_CLASSES
from core.event.models import Selection


class SlipsView(APIView):
    """Stateless parlay combiner — takes a list of selection ids, returns a
    snapshot with current odds and the combined decimal. We don't persist the
    slip here; that's a future feature."""

    # S-3/D4: POST /api/slips was anonymous; now authenticated (session+JWT) +
    # `user` throttle. SessionAuthentication enforces CSRF on the POST for
    # cookie-authed callers; JWT callers are exempt as usual.
    authentication_classes = V1_AUTHENTICATION_CLASSES
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def post(self, request):
        legs_in = request.data.get("legs") or []
        if not legs_in:
            return Response({"detail": "legs is required"}, status=status.HTTP_400_BAD_REQUEST)

        selection_ids = [leg.get("selection_id") for leg in legs_in if leg.get("selection_id")]
        selections = {s.id: s for s in Selection.objects.filter(id__in=selection_ids).select_related("market")}

        if len(selections) != len(selection_ids):
            missing = [sid for sid in selection_ids if sid not in selections]
            return Response({"detail": f"unknown selection ids: {missing}"}, status=400)

        legs_out = []
        combined = Decimal("1.0000")
        for sid in selection_ids:
            sel = selections[sid]
            combined *= sel.decimal_odds
            legs_out.append({
                "selection_id": sel.id,
                "market_id": sel.market_id,
                "type": sel.type,
                "label": sel.label,
                "decimal_odds": float(sel.decimal_odds),
            })

        return Response(
            {
                "slip_id": str(uuid.uuid4()),
                "legs": legs_out,
                "combined_decimal": float(combined.quantize(Decimal("0.0001"))),
            },
            status=status.HTTP_201_CREATED,
        )
