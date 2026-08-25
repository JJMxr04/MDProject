from django.urls import path

from core.event.views.api.events import EventDetailView, EventListView
from core.event.views.api.markets import EventMarketsView
from core.event.views.api.selections import SelectionMovementView
from core.event.views.api.slips import SlipsView

app_name = "core-event-api"

# Event.id is a CharField (SGO eventID, e.g. "mXCZTRJnbX8ib64z1h3D"); use <str:>.
# Selection.id is a 160-char synthesized string. Old route used <int:> which
# 404'd on every real selection.
urlpatterns = [
    path("events", EventListView.as_view(), name="event-list"),
    path("events/<str:event_id>", EventDetailView.as_view(), name="event-detail"),
    path("events/<str:event_id>/markets", EventMarketsView.as_view(), name="event-markets"),
    path("selections/<path:selection_id>/movement", SelectionMovementView.as_view(), name="selection-movement"),
    path("slips", SlipsView.as_view(), name="slips"),
]
