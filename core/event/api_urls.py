from django.urls import path

from core.event.views.api.events import EventDetailView, EventListView
from core.event.views.api.markets import EventMarketsView
from core.event.views.api.selections import SelectionMovementView
from core.event.views.api.slips import SlipsView

app_name = "core-event-api"

urlpatterns = [
    path("events", EventListView.as_view(), name="event-list"),
    path("events/<int:event_id>", EventDetailView.as_view(), name="event-detail"),
    path("events/<int:event_id>/markets", EventMarketsView.as_view(), name="event-markets"),
    path("selections/<int:selection_id>/movement", SelectionMovementView.as_view(), name="selection-movement"),
    path("slips", SlipsView.as_view(), name="slips"),
]
