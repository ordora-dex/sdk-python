"""
Example: Simple Market Making Bot

Strategy: Place one ASK and one BID around the current market price.
When an order is filled, place a new one.

WARNING: THIS IS AN EDUCATIONAL EXAMPLE ONLY — not an optimal trading strategy.
         Use small amounts and always test on testnet first.

Run:
    PRIVATE_KEY=0x... python examples/simple_bot.py
"""

import asyncio
import os
import signal
import time

from ordora_sdk import OrdoraSDK, PlaceAskNativeParams, PlaceBidParams

# ─── Bot Configuration ────────────────────────────────────────────────────────

PRIVATE_KEY = os.environ.get("PRIVATE_KEY", "")
if not PRIVATE_KEY:
    raise RuntimeError("Set environment variable PRIVATE_KEY")

CONFIG = {
    "pair":              "BNB_USDT",
    "base_token":        "0x0000000000000000000000000000000000000000",  # native BNB
    "quote_token":       "0x337610d27c682E347C9cD60BD4b3b107C9d34dDd",  # USDT testnet
    "spread_percent":    0.5,    # place at ±0.5% from last price
    "order_amount":      0.005,  # 0.005 BNB per order
    "check_interval":    15,     # seconds between ticks
    "max_orders_per_side": 1,
}

# ─── Bot State ────────────────────────────────────────────────────────────────

state = {
    "ask_order_id": None,
    "bid_order_id": None,
    "last_price":   0.0,
    "running":      True,
}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")


# ─── Bot Logic ────────────────────────────────────────────────────────────────

async def run() -> None:
    sdk = OrdoraSDK(private_key=PRIVATE_KEY, chain="bsc-testnet")

    log(f"Bot started — wallet: {sdk.address}")
    log(
        f"Pair: {CONFIG['pair']} | "
        f"Spread: ±{CONFIG['spread_percent']}% | "
        f"Amount: {CONFIG['order_amount']} BNB"
    )

    # Watch for trades that fill our orders
    async def on_my_trades(trades):
        if not trades:
            return
        latest = trades[0]
        if latest.ask_order_id == state["ask_order_id"]:
            log(f"ASK order FILLED @ {latest.price} | qty: {latest.base_amount}")
            state["ask_order_id"] = None
        if latest.bid_order_id == state["bid_order_id"]:
            log(f"BID order FILLED @ {latest.price} | qty: {latest.base_amount}")
            state["bid_order_id"] = None

    trade_task = asyncio.create_task(sdk.subscribe_my_trades(on_my_trades))

    # Main bot loop
    try:
        while state["running"]:
            try:
                await tick(sdk)
            except Exception as exc:
                log(f"Error: {exc}")
            await asyncio.sleep(CONFIG["check_interval"])
    finally:
        trade_task.cancel()
        log("Bot stopped.")


async def tick(sdk: OrdoraSDK) -> None:
    # 1. Fetch current market price
    ticker = await sdk.get_ticker(CONFIG["pair"])
    if not ticker:
        log("Ticker not found, skipping...")
        return

    current_price = float(ticker.last_price)
    if current_price == 0:
        log("Price is 0, skipping...")
        return

    log(f"Market price: {current_price} USDT")

    spread    = current_price * (CONFIG["spread_percent"] / 100)
    ask_price = round(current_price + spread, 4)  # sell higher
    bid_price = round(current_price - spread, 4)  # buy lower

    # 2. Check existing order statuses
    if state["ask_order_id"]:
        order = await sdk.get_order_by_id(state["ask_order_id"])
        if not order or order.status in ("FILLED", "CANCELLED"):
            status = order.status if order else "not found"
            log(f"ASK order {state['ask_order_id'][:8]}... is {status}")
            state["ask_order_id"] = None

    if state["bid_order_id"]:
        order = await sdk.get_order_by_id(state["bid_order_id"])
        if not order or order.status in ("FILLED", "CANCELLED"):
            status = order.status if order else "not found"
            log(f"BID order {state['bid_order_id'][:8]}... is {status}")
            state["bid_order_id"] = None

    # 3. Place a new ASK if none exists
    if not state["ask_order_id"]:
        try:
            log(f"Placing ASK @ {ask_price} USDT ({CONFIG['order_amount']} BNB)...")
            result = sdk.place_ask_native(PlaceAskNativeParams(
                quote_token = CONFIG["quote_token"],
                price       = ask_price,
                amount      = CONFIG["order_amount"],
            ))
            state["ask_order_id"] = result.order_id
            log(f"ASK placed: {result.order_id[:12]}... | tx: {result.tx_hash[:12]}...")
        except Exception as exc:
            log(f"Failed to place ASK: {exc}")
    else:
        order = await sdk.get_order_by_id(state["ask_order_id"])
        if order:
            drift = abs(float(order.price) - ask_price) / current_price * 100
            if drift > 1.0:
                log(f"ASK price drifted {drift:.2f}%, cancelling and re-placing...")
                sdk.cancel_order(state["ask_order_id"])
                state["ask_order_id"] = None
            else:
                log(f"ASK order active @ {order.price} (drift {drift:.2f}%)")

    # 4. Place a new BID if none exists
    if not state["bid_order_id"]:
        try:
            log(f"Placing BID @ {bid_price} USDT ({CONFIG['order_amount']} BNB)...")
            result = sdk.place_bid(PlaceBidParams(
                base_token  = CONFIG["base_token"],
                quote_token = CONFIG["quote_token"],
                price       = bid_price,
                amount      = CONFIG["order_amount"],
            ))
            state["bid_order_id"] = result.order_id
            log(f"BID placed: {result.order_id[:12]}... | tx: {result.tx_hash[:12]}...")
        except Exception as exc:
            log(f"Failed to place BID: {exc}")
    else:
        order = await sdk.get_order_by_id(state["bid_order_id"])
        if order:
            drift = abs(float(order.price) - bid_price) / current_price * 100
            if drift > 1.0:
                log(f"BID price drifted {drift:.2f}%, cancelling and re-placing...")
                sdk.cancel_order(state["bid_order_id"])
                state["bid_order_id"] = None
            else:
                log(f"BID order active @ {order.price} (drift {drift:.2f}%)")

    # 5. Print summary
    ask_str = state["ask_order_id"][:8] + "..." if state["ask_order_id"] else "empty"
    bid_str = state["bid_order_id"][:8] + "..." if state["bid_order_id"] else "empty"
    log(f"ASK: {ask_str} | BID: {bid_str}")


# ─── Graceful Shutdown ────────────────────────────────────────────────────────

async def shutdown(sdk: OrdoraSDK) -> None:
    log("Stopping bot and cancelling all active orders...")
    state["running"] = False

    for order_id, side in [
        (state["ask_order_id"], "ASK"),
        (state["bid_order_id"], "BID"),
    ]:
        if order_id:
            try:
                log(f"Cancelling {side}: {order_id[:12]}...")
                sdk.cancel_order(order_id)
            except Exception as exc:
                log(f"Failed to cancel {side}: {exc}")

    log("Bot stopped. All orders cleaned up.")


async def main() -> None:
    sdk  = OrdoraSDK(private_key=PRIVATE_KEY, chain="bsc-testnet")
    loop = asyncio.get_running_loop()

    def _on_sigint():
        asyncio.create_task(shutdown(sdk))

    loop.add_signal_handler(signal.SIGINT, _on_sigint)

    await run()


if __name__ == "__main__":
    asyncio.run(main())
