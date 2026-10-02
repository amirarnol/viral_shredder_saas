"""Simulated crypto payment gateway.

Creates deposit orders against the configured USDT wallets, exposes the deposit
instructions the buyer pays to, and settles orders.

Settlement model
----------------
PAYMENT_DEMO_MODE=1  - a background task marks the order PAID after
                       PAYMENT_DEMO_CONFIRM_AFTER seconds. Nothing touches a chain;
                       this exists to demo the upgrade flow end to end.
PAYMENT_DEMO_MODE=0  - orders stay PENDING and an operator confirms them through
                       the admin endpoint (or the manual support channels).

Wiring a real watcher later means replacing `settle_pending_orders` with a
TronGrid/BSC scan for incoming USDT transfers to these wallets and matching on
the exact amount; the order_ref is carried as the memo/amount discriminator.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import time

from .config import settings
from . import database as db

log = logging.getLogger("viral_shredder.payments")

# Networks the deposit UI offers. All settle in USDT at the Pro price.
NETWORKS = [
    {
        "id": "trc20",
        "label": "USDT - TRC20 (Tron)",
        "currency": "USDT",
        "address": settings.usdt_trc20_wallet,
        "note": "Lowest fees. Estimated ~1 minute to confirm.",
    },
    {
        "id": "bep20",
        "label": "USDT - BEP20 (BNB Smart Chain)",
        "currency": "USDT",
        "address": settings.usdt_bep20_wallet,
        "note": "Cheap and fast. Estimated ~1-3 minutes to confirm.",
    },
    {
        "id": "binance_pay",
        "label": "Binance Pay (send to Binance ID)",
        "currency": "USDT",
        "address": f"Binance ID: {settings.binance_id}",
        "note": "No network fee. Open Binance, scan or paste the ID, send USDT.",
    },
]


def networks() -> list[dict]:
    return NETWORKS


def amount_for_plan(plan_id: str) -> float:
    from .config import plan_for

    return float(plan_for(plan_id)["price_usd"])


def make_order_ref(user_id: int) -> str:
    seed = f"{user_id}:{time.time()}:{secrets.token_hex(8)}".encode()
    digest = hashlib.sha256(seed).hexdigest()
    return f"VS-{digest[:6].upper()}-{digest[6:10].upper()}"


def create_order(user_id: int, plan_id: str = "pro", network_id: str = "trc20") -> dict:
    """Create a PENDING deposit order and return everything the UI needs."""
    network = next((n for n in NETWORKS if n["id"] == network_id), NETWORKS[0])
    amount = amount_for_plan(plan_id)
    order_ref = make_order_ref(user_id)

    payment_id = db.create_payment(
        user_id=user_id,
        order_ref=order_ref,
        amount_usd=amount,
        currency=network["currency"],
        network=network["id"],
    )

    return {
        "payment_id": payment_id,
        "order_ref": order_ref,
        "amount_usd": amount,
        "amount_crypto": amount,  # 1 USDT = 1 USD
        "currency": network["currency"],
        "network": network["label"],
        "network_id": network["id"],
        "address": network["address"],
        "note": network["note"],
        "status": "pending",
        "demo": settings.payment_demo_mode,
    }


def order_status(payment_id: int) -> str:
    row = db.get_payment(payment_id)
    return row["status"] if row else "unknown"


def settle_pending_orders() -> int:
    """Demo settlement pass. Returns the number of orders closed."""
    if not settings.payment_demo_mode:
        return 0
    closed = 0
    for row in db.pending_payments():
        age = time.time() - _epoch(row["created_at"])
        if age >= settings.payment_demo_confirm_after:
            tx = f"0x{hashlib.sha256(row['order_ref'].encode()).hexdigest()[:64]}"
            db.confirm_payment(row["id"], tx_hash=tx)
            db.set_user_plan(row["user_id"], "pro")
            log.info("demo-settled order %s (user %s) -> pro", row["order_ref"], row["user_id"])
            closed += 1
    return closed


def admin_confirm(payment_id: int) -> bool:
    """Manual confirmation used when demo mode is off."""
    row = db.get_payment(payment_id)
    if not row or row["status"] != "pending":
        return False
    db.confirm_payment(payment_id, tx_hash="manual-confirmation")
    db.set_user_plan(row["user_id"], "pro")
    return True


async def settlement_loop() -> None:
    """Background task: periodically settle demo orders."""
    while True:
        try:
            settle_pending_orders()
        except Exception:  # pragma: no cover - keep the loop alive
            log.exception("settlement pass failed")
        await asyncio.sleep(10)


def _epoch(iso: str) -> float:
    from datetime import datetime

    try:
        return datetime.fromisoformat(iso).timestamp()
    except Exception:
        return time.time()
