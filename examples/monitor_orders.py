"""
Example: Monitor all trading activity in real-time

Run:
    PRIVATE_KEY=0x... python examples/monitor_orders.py
"""

import asyncio
import os
import signal

from ordora_sdk import OrdoraSDK

PRIVATE_KEY = os.environ.get("PRIVATE_KEY", "")
if not PRIVATE_KEY:
    raise RuntimeError("Set environment variable PRIVATE_KEY")


async def main() -> None:
    sdk = OrdoraSDK(private_key=PRIVATE_KEY, chain="bsc-testnet")

    print("Monitor active for wallet:", sdk.address)
    print("Press Ctrl+C to stop\n")

    # ── Monitor 1: Open Orders ────────────────────────────────────────────────
    async def on_orders(orders):
        print(f"[Orders] {len(orders)} open order(s):")
        for o in orders:
            filled_pct = float(o.base_filled) / float(o.amount) * 100 if float(o.amount) else 0
            print(f"  {o.pair_symbol} {o.side} {o.status} | Price: {o.price} | Fill: {filled_pct:.1f}%")
        if not orders:
            print("  (no open orders)")

    # ── Monitor 2: Incoming Trades ────────────────────────────────────────────
    async def on_my_trades(trades):
        if not trades:
            return
        t      = trades[0]
        is_buy = t.trade_type == "buy"
        arrow  = "▲ BUY" if is_buy else "▼ SELL"
        print(f"[Trade] {arrow} {t.pair_symbol} @ {t.price} | Amount: {t.base_amount} | {t.traded_at}")

    # ── Monitor 3: Locked Escrow ──────────────────────────────────────────────
    async def on_locked(assets):
        if not assets:
            return
        print("[Escrow] Locked:")
        for a in assets:
            print(f"  {a.locked_human} {a.token_symbol} ({a.order_count} orders)")

    # ── Monitor 4: Live BNB_USDT Market Trades ────────────────────────────────
    async def on_market_trades(trades):
        if not trades:
            return
        t     = trades[0]
        arrow = "▲" if t.trade_type == "buy" else "▼"
        print(f"[Market BNB_USDT] {arrow} Price: {t.price} | Vol: {t.base_amount} | {t.traded_at}")

    # ── Monitor 5: On-chain Events ────────────────────────────────────────────
    stop_placed = sdk.on_order_placed(
        lambda order_id, tx: print(f"[On-chain] PLACED: {order_id[:12]}... tx: {tx[:12]}...")
    )
    stop_matched = sdk.on_order_matched(
        lambda ask, bid, tx: print(f"[On-chain] MATCHED: ask={ask[:12]}... tx: {tx[:12]}...")
    )
    stop_cancelled = sdk.on_order_cancelled(
        lambda order_id, tx: print(f"[On-chain] CANCELLED: {order_id[:12]}... tx: {tx[:12]}...")
    )

    # Run all subscriptions concurrently
    tasks = [
        asyncio.create_task(sdk.subscribe_open_orders(on_orders)),
        asyncio.create_task(sdk.subscribe_my_trades(on_my_trades)),
        asyncio.create_task(sdk.subscribe_locked_assets(on_locked)),
        asyncio.create_task(sdk.subscribe_live_trades("BNB_USDT", on_market_trades, limit=5)),
    ]

    loop = asyncio.get_running_loop()

    def _shutdown():
        print("\nStopping monitor...")
        stop_placed()
        stop_matched()
        stop_cancelled()
        for t in tasks:
            t.cancel()

    loop.add_signal_handler(signal.SIGINT, _shutdown)

    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(main())
