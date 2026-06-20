from .available_events import available_events_for_match
from .duel import duel_events_view, duels_page_view, send_duel_view
from .eventMarket import event_markets
from .eventOutcome import event_outcomes
from .myMatchDetail import (
    my_match_detail_view,
    pick_on_locked_slot,
    player_2_select_outcome,
    rematch_view,
    upload_pick,
)
from .myMatchList import my_match_list_view
from .publicMatchList import (
    accept_public_match_view,
    create_public_match_view,
    match_availability_view,
    public_match_detail_view,
    public_match_list_view,
)
