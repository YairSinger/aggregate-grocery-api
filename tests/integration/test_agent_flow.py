#!/usr/bin/env python3
"""
Integration test — full agent ordering flow.

Tests all 10 agent endpoints end-to-end against the live backend.
The Playwright step is simulated via a direct DB update so the full
confirmation flow can be tested without real Shufersal credentials.

Run:
    python3 tests/integration/test_agent_flow.py

Requirements: backend on localhost:8030, DB in docker (grocery_db container).
"""

import subprocess
import sys
import time

import requests

BASE = "http://localhost:8030/api/v1"
EMAIL = "yairsinger52@gmail.com"
HEADERS = {"X-User-Email": EMAIL, "Content-Type": "application/json"}

PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
INFO = "\033[33m→\033[0m"

_failures = []


def step(name):
    print(f"\n{INFO} {name}")

def ok(msg):
    print(f"  {PASS} {msg}")

def fail(msg):
    print(f"  {FAIL} {msg}")
    _failures.append(msg)

def check(label, got, expected):
    if got == expected:
        ok(f"{label}: {got!r}")
    else:
        fail(f"{label}: expected {expected!r}, got {got!r}")

def has(label, key, obj):
    if key in obj:
        ok(f"{label} has '{key}'")
    else:
        fail(f"{label} missing '{key}' — keys: {list(obj.keys())}")

def db(sql):
    r = subprocess.run(
        ["docker", "exec", "grocery_db", "psql", "-U", "postgres",
         "-d", "grocery_aggregator", "-t", "-c", sql],
        capture_output=True, text=True,
    )
    return r.stdout.strip()

def simulate_cart_built(order_id):
    """Bypass Playwright: directly set order to AWAITING_CONFIRMATION with fake cart_url.
    NOTE: DB enum stores uppercase names (AWAITING_CONFIRMATION not awaiting_confirmation)."""
    db(f"""UPDATE orders SET status='AWAITING_CONFIRMATION',
           cart_url='https://shufersal.co.il/fake-cart-{order_id[:8]}',
           delivery_date='Tuesday 18:00-21:00'
           WHERE id='{order_id}'""")

def cleanup(pending_ids, order_id, aggregate_id):
    if order_id:
        db(f"DELETE FROM order_items WHERE order_id='{order_id}'")
        db(f"DELETE FROM orders WHERE id='{order_id}'")
    for pid in pending_ids:
        db(f"DELETE FROM pending_items WHERE id='{pid}'")
    if aggregate_id:
        db(f"DELETE FROM aggregate_items WHERE aggregate_id='{aggregate_id}'")
        db(f"DELETE FROM aggregates WHERE id='{aggregate_id}'")


def run():
    pending_ids = []
    order_id = None
    new_agg_id = None

    try:
        # 1 — health
        step("1. Health check")
        r = requests.get(BASE.replace("/api/v1", "") + "/health")
        check("status", r.json().get("status"), "ok")

        # 2 — add free-text pending item
        step("2. add_pending_item (unmatched)")
        r = requests.post(f"{BASE}/agent/pending-items", headers=HEADERS,
                          json={"item_name": "test_eggs_integration", "qty": 12, "unit": "UNITS"})
        check("HTTP", r.status_code, 201)
        egg = r.json()
        has("response", "id", egg)
        check("status", egg["status"], "pending")
        check("aggregate_id", egg["aggregate_id"], None)
        pending_ids.append(egg["id"])

        # 3 — get pending items
        step("3. get_pending_items")
        r = requests.get(f"{BASE}/agent/pending-items", headers=HEADERS)
        check("HTTP", r.status_code, 200)
        data = r.json()
        has("response", "total", data)
        has("response", "unmatched", data)
        check("egg in list", any(i["id"] == egg["id"] for i in data["items"]), True)

        # 4 — list aggregates
        step("4. list_aggregates")
        r = requests.get(f"{BASE}/agent/aggregates", headers=HEADERS)
        check("HTTP", r.status_code, 200)
        aggs = r.json()["aggregates"]
        ok(f"found {len(aggs)} aggregates: {[a['name'] for a in aggs]}")

        # 5 — ensure_aggregate (create new)
        step("5. ensure_aggregate — create")
        AGG = "test_aggregate_integration"
        r = requests.post(f"{BASE}/agent/aggregates/ensure", headers=HEADERS,
                          json={"name": AGG, "unit_of_measure": "UNITS", "search_hint": "חלב 3"})
        check("HTTP", r.status_code, 201)
        agg_data = r.json()
        check("created", agg_data["created"], True)
        new_agg_id = agg_data["id"]
        ok(f"id: {new_agg_id}, linked: {agg_data.get('items_linked', [])}")

        # 5b — idempotent
        step("5b. ensure_aggregate — idempotent")
        r = requests.post(f"{BASE}/agent/aggregates/ensure", headers=HEADERS,
                          json={"name": AGG, "unit_of_measure": "UNITS"})
        check("HTTP", r.status_code, 201)
        check("created=False", r.json()["created"], False)
        check("same id", r.json()["id"], new_agg_id)

        # 6 — add matched pending item
        step("6. add_pending_item (matched)")
        r = requests.post(f"{BASE}/agent/pending-items", headers=HEADERS,
                          json={"item_name": AGG, "qty": 2, "unit": "UNITS",
                                "aggregate_id": new_agg_id})
        check("HTTP", r.status_code, 201)
        matched = r.json()
        check("aggregate_id set", matched["aggregate_id"], new_agg_id)
        pending_ids.append(matched["id"])

        # 7 — optimize_cart
        step("7. optimize_cart")
        r = requests.post(f"{BASE}/agent/optimize", headers=HEADERS,
                          json={"user_lat": 31.89, "user_lng": 35.01, "max_distance_km": 100.0})
        if r.status_code != 200:
            fail(f"HTTP {r.status_code}: {r.json()}")
        else:
            check("HTTP", r.status_code, 200)
            opt = r.json()
            has("response", "order_id", opt)
            has("response", "store_name", opt)
            has("response", "total_cost", opt)
            has("response", "items", opt)
            has("response", "unresolved", opt)
            order_id = opt["order_id"]
            ok(f"order_id: {order_id}")
            ok(f"store: {opt.get('store_name')} — ₪{opt.get('total_cost')}")
            ok(f"assigned: {len(opt.get('items', []))}, unresolved: {len(opt.get('unresolved', []))}")

        if not order_id:
            fail("Cannot continue without order_id")
            return 1

        # 8 — get order status (PENDING)
        step("8. get_order_status → PENDING")
        r = requests.get(f"{BASE}/agent/orders/{order_id}", headers=HEADERS)
        check("HTTP", r.status_code, 200)
        check("status", r.json()["status"], "pending")

        # 9 — simulate cart built (bypass Playwright)
        step("9. Simulate cart_built (DB direct — bypasses Playwright)")
        simulate_cart_built(order_id)
        time.sleep(0.3)

        # 10 — get order status (AWAITING_CONFIRMATION)
        step("10. get_order_status → AWAITING_CONFIRMATION")
        r = requests.get(f"{BASE}/agent/orders/{order_id}", headers=HEADERS)
        check("HTTP", r.status_code, 200)
        od = r.json()
        check("status", od["status"], "awaiting_confirmation")
        has("response", "cart_url", od)
        ok(f"cart_url: {od.get('cart_url')}")

        # 11 — store_confirmation
        step("11. store_confirmation")
        r = requests.post(f"{BASE}/agent/orders/{order_id}/confirm", headers=HEADERS,
                          json={"confirmation_number": "TEST-12345"})
        check("HTTP", r.status_code, 200)
        cd = r.json()
        check("status", cd["status"], "placed")
        check("confirmation_number", cd["confirmation_number"], "TEST-12345")
        has("response", "placed_at", cd)

        # 12 — final status check
        step("12. get_order_status → PLACED")
        r = requests.get(f"{BASE}/agent/orders/{order_id}", headers=HEADERS)
        check("HTTP", r.status_code, 200)
        check("final status", r.json()["status"], "placed")

        # 13 — skip items
        step("13. skip_items")
        r = requests.post(f"{BASE}/agent/pending-items/skip", headers=HEADERS,
                          json={"item_ids": [egg["id"]]})
        check("HTTP", r.status_code, 200)
        check("skipped", r.json()["skipped"], 1)

        # 14 — remove item from aggregate
        step("14. remove_item_from_aggregate")
        row = db(f"SELECT item_id FROM aggregate_items WHERE aggregate_id='{new_agg_id}' LIMIT 1")
        if row:
            r = requests.delete(f"{BASE}/agent/aggregates/{new_agg_id}/items/{row.strip()}",
                                headers=HEADERS)
            check("HTTP", r.status_code, 200)
            check("removed", r.json()["removed"], True)
        else:
            ok("no items linked — skip")

    except Exception as exc:
        fail(f"Unexpected exception: {exc}")
        import traceback; traceback.print_exc()

    finally:
        step("Cleanup")
        cleanup(pending_ids, order_id, new_agg_id)
        ok("test data removed")

    print("\n" + "─" * 50)
    if _failures:
        print(f"\n{FAIL} {len(_failures)} failure(s):")
        for f in _failures:
            print(f"    • {f}")
        return 1
    print(f"\n{PASS} All steps passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
