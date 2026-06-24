"""
Example: Place an order and monitor its status until FILLED

Run:
    pip install -r requirements.txt
    PRIVATE_KEY=0x... python examples/place_order.py
"""

import asyncio
import os

from ordora_sdk import OrdoraSDK, PlaceAskNativeParams, PlaceBidParams

# ─── Configuration ────────────────────────────────────────────────────────────
# NEVER store private keys in code — use environment variables

PRIVATE_KEY = os.environ.get("PRIVATE_KEY", "")
if not PRIVATE_KEY:
    raise RuntimeError("Set environment variable PRIVATE_KEY")

# Token addresses on BSC Testnet
USDT = "0x337610d27c682E347C9cD60BD4b3b107C9d34dDd"
BNB  = "0x0000000000000000000000000000000000000000"  # native


async def main() -> None:
    sdk = OrdoraSDK(private_key=PRIVATE_KEY, chain="bsc-testnet")

    print("Wallet:", sdk.address)

    # ── 1. Check balances ────────────────────────────────────────────────────
    bnb_balance = sdk.get_bnb_balance()
    print(f"BNB balance: {bnb_balance / 1e18:.6f} BNB")

    # ── 2. Check active markets ──────────────────────────────────────────────
    markets = await sdk.get_markets()
    print("Active markets:", ", ".join(m.pair_symbol for m in markets))

    # ── 3. Check BNB_USDT ticker ─────────────────────────────────────────────
    ticker = await sdk.get_ticker("BNB_USDT")
    if ticker:
        print(f"BNB_USDT — Price: {ticker.last_price}, 24h Volume: {ticker.base_volume_24h}")

    # ── 4. Place ASK order (sell BNB) ────────────────────────────────────────
    print("\nPlacing ASK order: sell 0.01 BNB @ 310.00 USDT...")

    ask_result = sdk.place_ask_native(PlaceAskNativeParams(
        quote_token = USDT,
        price       = 310.00,  # 1 BNB = 310 USDT
        amount      = 0.01,    # sell 0.01 BNB
    ))

    print("ASK order placed!")
    print("  Order ID:", ask_result.order_id)
    print("  TX Hash: ", ask_result.tx_hash)

    # ── 5. Place BID order (buy BNB) ─────────────────────────────────────────
    print("\nPlacing BID order: buy 0.01 BNB @ 308.00 USDT...")

    bid_result = sdk.place_bid(PlaceBidParams(
        base_token  = BNB,
        quote_token = USDT,
        price       = 308.00,  # buy at 308 USDT
        amount      = 0.01,    # buy 0.01 BNB
    ))

    print("BID order placed!")
    print("  Order ID:", bid_result.order_id)
    print("  TX Hash: ", bid_result.tx_hash)

    # ── 6. Monitor ASK order status ───────────────────────────────────────────
    print("\nMonitoring ASK order status...")

    filled_event = asyncio.Event()

    async def on_status(order):
        if order is None:
            return
        print(f"Status: {order.status} | Filled: {order.base_filled} / {order.amount}")
        if order.status in ("FILLED", "CANCELLED"):
            filled_event.set()

    monitor_task = asyncio.create_task(
        sdk.subscribe_order_status(ask_result.order_id, on_status)
    )

    try:
        # Timeout after 30 seconds
        await asyncio.wait_for(filled_event.wait(), timeout=30.0)
    except asyncio.TimeoutError:
        print("Timeout — cancelling order...")
        tx = sdk.cancel_order(ask_result.order_id)
        print(f"Order cancelled. TX: {tx}")
    finally:
        monitor_task.cancel()

    # ── 7. View open orders ───────────────────────────────────────────────────
    open_orders = await sdk.get_open_orders()
    print(f"\nOpen orders now: {len(open_orders)}")
    for o in open_orders:
        print(f"  {o.pair_symbol} {o.side} @ {o.price} — {o.status}")

    # ── 8. View locked assets ─────────────────────────────────────────────────
    locked = await sdk.get_locked_assets()
    for a in locked:
        print(f"  Locked: {a.locked_human} {a.token_symbol} ({a.order_count} orders)")


if __name__ == "__main__":
    asyncio.run(main())
