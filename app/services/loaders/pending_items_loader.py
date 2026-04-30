"""
Pending items loader — DB PendingItems → List[WantedItem].

STUB — Phase 2 of agent integration plan.

This loader will resolve PendingItem rows (free-text item names added by the
home monitoring agent) into WantedItems with CandidatePrices, using the
LLM-matched aggregate_id stored on each PendingItem after the agent's
ensure_aggregate() call.

Once implemented, the optimize_cart() MCP tool calls this loader instead
of the shopping list loader, then passes the result to the same
basket_optimizer.optimize_single_store().
"""

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.types import WantedItem


def load_wanted_items_from_pending(
    db: Session,
    user_id: UUID,
    user_lat: float,
    user_lng: float,
    max_distance_km: float = 5.0,
) -> List[WantedItem]:
    """
    Load WantedItems from the user's pending items list.
    Only includes items with status='pending'.
    Items without a matched aggregate_id are returned with empty candidates
    (optimizer will mark them unresolved).
    """
    raise NotImplementedError(
        "pending_items_loader is a Phase-2 stub. "
        "Implement after PendingItem DB model is added (Phase 1 of agent integration)."
    )
