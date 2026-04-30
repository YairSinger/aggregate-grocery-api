"""
Pure basket optimization.

optimize_single_store(wanted) → OptimizationResult

No DB access. No HTTP. No side effects.
Takes a list of WantedItems (each with pre-fetched CandidatePrices) and returns
the single store that covers the most items at the lowest total cost.

Items with no candidates in any store are returned as globally unresolved.
Items that exist in some stores but not the chosen one are also in unresolved —
the caller (MCP tool / route handler) notifies the user about them.

Alternatives: all other stores with full basket coverage, sorted by cost ascending.
"""

from decimal import Decimal, ROUND_UP
from typing import List, Optional
from uuid import UUID

from app.services.types import (
    AlternativeStore,
    AssignedItem,
    CandidatePrice,
    OptimizationResult,
    WantedItem,
)


def optimize_single_store(wanted: List[WantedItem]) -> OptimizationResult:
    """
    Find the single store that covers the most WantedItems at lowest total cost.

    Scoring priority:
      1. Most items covered (higher = better)
      2. Lowest total cost (lower = better)

    Returns the best result. `unresolved` contains items with no candidate
    at the chosen store (includes globally unresolved items with no candidates anywhere).
    `alternatives` contains all other full-coverage stores, sorted cheapest first.
    """
    if not wanted:
        raise ValueError("wanted list is empty")

    globally_unresolved = [w for w in wanted if not w.candidates]
    resolvable = [w for w in wanted if w.candidates]

    if not resolvable:
        return OptimizationResult(
            store_id=None,
            store_name="",
            chain_name="",
            distance_km=0.0,
            assigned_items=[],
            total_cost=Decimal("0"),
            unresolved=globally_unresolved,
        )

    # Collect unique stores from all candidates
    stores: dict[UUID, tuple[str, str, float]] = {}
    for w in resolvable:
        for c in w.candidates:
            if c.store_id not in stores:
                stores[c.store_id] = (c.store_name, c.chain_name, c.distance_km)

    best: Optional[OptimizationResult] = None
    full_coverage_stores: list[tuple[Decimal, AlternativeStore]] = []  # (cost, store)

    for store_id, (store_name, chain_name, distance_km) in stores.items():
        assigned, store_unresolved, total = _score_store(
            store_id, resolvable
        )
        result = OptimizationResult(
            store_id=store_id,
            store_name=store_name,
            chain_name=chain_name,
            distance_km=distance_km,
            assigned_items=assigned,
            total_cost=total,
            unresolved=store_unresolved + globally_unresolved,
        )

        if best is None or _is_better(result, best):
            best = result

        if not store_unresolved:  # full coverage
            full_coverage_stores.append((
                total,
                AlternativeStore(
                    store_id=store_id,
                    store_name=store_name,
                    chain_name=chain_name,
                    total_cost=total,
                ),
            ))

    # Alternatives = full-coverage stores cheaper than best, sorted ascending
    full_coverage_stores.sort(key=lambda t: t[0])
    best.alternatives = [
        alt for _, alt in full_coverage_stores
        if alt.store_id != best.store_id
    ]

    return best


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _score_store(
    store_id: UUID,
    resolvable: List[WantedItem],
) -> tuple[List[AssignedItem], List[WantedItem], Decimal]:
    """
    For a given store, pick the cheapest candidate per WantedItem.
    Returns (assigned, unresolved, total_cost).
    """
    assigned: List[AssignedItem] = []
    unresolved: List[WantedItem] = []
    total = Decimal("0")

    for w in resolvable:
        store_candidates = [c for c in w.candidates if c.store_id == store_id]
        if not store_candidates:
            unresolved.append(w)
            continue

        best_candidate: CandidatePrice = min(
            store_candidates, key=lambda c: c.price_per_unit
        )
        pkg_qty = (
            Decimal(str(best_candidate.package_quantity))
            if best_candidate.package_quantity > 0
            else Decimal("1")
        )
        packages = (Decimal(str(w.desired_amount)) / pkg_qty).quantize(
            Decimal("1"), rounding=ROUND_UP
        )
        cost = best_candidate.effective_price * packages
        total += cost

        assigned.append(AssignedItem(
            name=w.name,
            aggregate_id=w.aggregate_id,
            item_id=best_candidate.item_id,
            item_name=best_candidate.item_name,
            store_id=store_id,
            price_per_unit=best_candidate.price_per_unit,
            packages_needed=packages,
            cost=cost,
        ))

    return assigned, unresolved, total


def _is_better(candidate: OptimizationResult, current_best: OptimizationResult) -> bool:
    """More covered items wins. On a tie, lower cost wins."""
    c_covered = len(candidate.assigned_items)
    b_covered = len(current_best.assigned_items)
    if c_covered != b_covered:
        return c_covered > b_covered
    return candidate.total_cost < current_best.total_cost
