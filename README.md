# Ordora DEX — Python SDK

Official Python SDK for interacting with Ordora DEX from Python 3.10+ applications.
Supports placing orders, cancelling orders, real-time status monitoring, and reading market data.

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Reference](#api-reference)
  - [Balance & Approval](#balance--approval)
  - [Place Order](#place-order)
  - [Cancel Order](#cancel-order)
  - [Read Data (Hasura)](#read-data-hasura)
  - [Real-time Subscriptions](#real-time-subscriptions)
  - [On-chain Events](#on-chain-events)
  - [Utilities](#utilities)
- [Types](#types)
- [Full Examples](#full-examples)
- [Running Examples](#running-examples)
- [Security](#security)
- [Error Reference](#error-reference)

---

## Installation

**Prerequisites:** Python 3.10+

```bash
cd sdk/python
pip install -r requirements.txt
```

**Core dependencies:**

| Package | Purpose |
|---|---|
| `web3` v6 | Blockchain interaction (sign, send tx) |
| `gql[aiohttp,websockets]` | Hasura GraphQL queries and WebSocket subscriptions |
| `aiohttp` | Async HTTP transport |
| `python-dotenv` | Load `.env` files |

---

## Quick Start

```python
import asyncio
import os
from ordora_sdk import OrdoraSDK, PlaceAskNativeParams

# Initialize with a private key (default chain: bsc-testnet)
sdk = OrdoraSDK(private_key=os.environ["PRIVATE_KEY"])

print("Wallet:", sdk.address)

# Check BNB balance (synchronous)
balance = sdk.get_bnb_balance()
print(f"BNB: {balance / 1e18:.6f}")

# Fetch active markets (async)
markets = asyncio.run(sdk.get_markets())
for m in markets:
    print(m.pair_symbol)

# Sell 0.01 BNB at 310 USDT (synchronous)
result = sdk.place_ask_native(PlaceAskNativeParams(
    quote_token = "0x337610d27c682E347C9cD60BD4b3b107C9d34dDd",  # USDT testnet
    price       = 310.00,
    amount      = 0.01,
))
print("Order ID:", result.order_id)
print("TX Hash: ", result.tx_hash)
```

> **Important:** Store private keys in environment variables — never hardcode them.

---

## Configuration

### Constructor

```python
sdk = OrdoraSDK(
    private_key   = "0x...",
    chain         = "bsc-testnet",     # or "bsc-mainnet" or a ChainConfig object
    hasura_url    = None,              # override Hasura HTTP URL
    hasura_ws_url = None,              # override Hasura WebSocket URL
)
```

### Supported Chains

| Chain | `chain` value | Chain ID | Contract |
|---|---|---|---|
| BSC Testnet | `"bsc-testnet"` | 97 | `0x9466a9259075859E14897AE556ca0B449BdF6e6D` |
| BSC Mainnet | `"bsc-mainnet"` | 56 | (not yet deployed) |

### Custom Chain

```python
from ordora_sdk import OrdoraSDK, ChainConfig

sdk = OrdoraSDK(
    private_key = "0x...",
    chain = ChainConfig(
        chain_id         = 97,
        rpc_url          = "https://rpc-custom.example.com",
        contract_address = "0x...",
        wbnb_address     = "0x...",
        explorer_url     = "https://testnet.bscscan.com",
    ),
)
```

### Environment Variables

Create a `.env` file in your project root:

```env
PRIVATE_KEY=0x...trader_wallet_private_key...
```

Load with `python-dotenv`:
```python
from dotenv import load_dotenv
import os

load_dotenv()
sdk = OrdoraSDK(private_key=os.environ["PRIVATE_KEY"])
```

### Sync vs Async

| Method type | How to call |
|---|---|
| On-chain reads & writes | Synchronous (blocking) — call directly |
| Hasura queries | `async` coroutine — use `asyncio.run()` or `await` |
| Hasura subscriptions | `async` coroutine — run as `asyncio.create_task()` |

---

## API Reference

### Balance & Approval

#### `sdk.get_bnb_balance() -> int`

Get the wallet's native BNB balance in wei.

```python
balance = sdk.get_bnb_balance()
print(f"{balance / 1e18:.6f} BNB")
```

#### `sdk.get_token_balance(token_address: str) -> int`

Get the ERC20 token balance in wei.

```python
USDT = "0x337610d27c682E347C9cD60BD4b3b107C9d34dDd"
balance = sdk.get_token_balance(USDT)
```

#### `sdk.approve_token(token_address: str) -> ApprovalResult`

Approve an ERC20 token for the DEX contract (unlimited).

> The SDK does this **automatically** when placing an order. Call this only to pre-approve.

```python
result = sdk.approve_token(USDT)
if result.approved:
    print("Approved, TX:", result.tx_hash)
else:
    print("Already approved")
```

---

### Place Order

All place order methods:
- Automatically encode price/amount from **human-readable → raw wei**
- Automatically approve ERC20 tokens if allowance is insufficient
- Automatically generate a unique `order_id` and `nonce`
- Return `PlaceOrderResult(order_id, tx_hash)`

#### `sdk.place_ask_token(params)` — Sell an ERC20 Token

```python
from ordora_sdk import PlaceAskTokenParams

result = sdk.place_ask_token(PlaceAskTokenParams(
    base_token  = "0xTokenToSell...",
    quote_token = "0xUSDT...",
    price       = 312.50,   # 1 token = 312.50 USDT
    amount      = 1.5,      # sell 1.5 tokens
))
print("Order ID:", result.order_id)
```

#### `sdk.place_ask_native(params)` — Sell Native BNB

BNB is sent as `msg.value` — no approval needed.

```python
from ordora_sdk import PlaceAskNativeParams

result = sdk.place_ask_native(PlaceAskNativeParams(
    quote_token = "0xUSDT...",
    price       = 312.50,   # 1 BNB = 312.50 USDT
    amount      = 0.5,      # sell 0.5 BNB
))
```

#### `sdk.place_bid(params)` — Buy a Token

Auto-approves the quote token if ERC20, or sends BNB if native.

```python
from ordora_sdk import PlaceBidParams

result = sdk.place_bid(PlaceBidParams(
    base_token  = "0xTokenToBuy...",
    quote_token = "0xUSDT...",
    price       = 310.00,   # buy at 310.00 USDT per token
    amount      = 2.0,      # buy 2 tokens
))
```

**Escrow required for BID:**
The SDK calculates this automatically: `escrow = price × amount`

---

### Cancel Order

#### `sdk.cancel_order(order_id: str) -> str`

Cancel your own order. Returns the transaction hash.

```python
tx_hash = sdk.cancel_order("0x1a2b3c...")
print("Cancelled, TX:", tx_hash)
```

---

### Read Data (Hasura)

All Hasura methods are `async`. Data is already **human-readable** — no conversion needed.

#### Orders

```python
import asyncio

# Open orders for this wallet (OPEN and PARTIAL)
open_orders = asyncio.run(sdk.get_open_orders())

# Full order history with pagination
result = asyncio.run(sdk.get_order_history(limit=20, offset=0))
print(f"Total: {result.total_count}, Has next: {result.has_next_page}")
for o in result.data:
    print(o.order_id, o.status)

# Single order by ID
order = asyncio.run(sdk.get_order_by_id("0x1a2b..."))
if order:
    print(order.status, order.base_filled)
```

#### Trades

```python
# All trades for this wallet (as seller or buyer)
result = asyncio.run(sdk.get_my_trades(limit=50))

# Trade history for a pair
trades = asyncio.run(sdk.get_trades_by_pair("BNB_USDT", limit=30))

# All fills for a specific order
fills = asyncio.run(sdk.get_trades_by_order("0x1a2b..."))
for t in fills:
    print(f"Filled @ {t.price}, qty: {t.base_amount}")
```

#### Market & Ticker

```python
markets = asyncio.run(sdk.get_markets())

tickers = asyncio.run(sdk.get_all_tickers())

ticker = asyncio.run(sdk.get_ticker("BNB_USDT"))
if ticker:
    print("Last price:", ticker.last_price)
    print("24h change:", ticker.price_change_pct_24h, "%")
    print("Volume:    ", ticker.base_volume_24h, "BNB")
```

#### Assets

```python
tokens = asyncio.run(sdk.get_tokens())

locked = asyncio.run(sdk.get_locked_assets())
for a in locked:
    print(f"{a.locked_human} {a.token_symbol} ({a.order_count} active orders)")
```

---

### Real-time Subscriptions

Subscriptions are `async` coroutines that stream data via WebSocket until cancelled.
Run them as `asyncio.create_task()` alongside other work.

#### Subscribe Open Orders

```python
import asyncio
from ordora_sdk import OrdoraSDK

async def main():
    sdk = OrdoraSDK(private_key="0x...")

    async def on_orders(orders):
        print(f"{len(orders)} open order(s)")
        for o in orders:
            print(f"  {o.pair_symbol} {o.side} @ {o.price}")

    task = asyncio.create_task(sdk.subscribe_open_orders(on_orders))
    await asyncio.sleep(60)   # run for 60 seconds
    task.cancel()

asyncio.run(main())
```

#### Subscribe to a Single Order's Status

```python
async def on_status(order):
    if order is None:
        return
    print("Status:", order.status, "| Fill:", order.base_filled)
    if order.status == "FILLED":
        print("Order fully filled!")
        task.cancel()

task = asyncio.create_task(
    sdk.subscribe_order_status("0x1a2b...", on_status)
)
```

#### Subscribe to Incoming Trades

```python
async def on_trades(trades):
    if not trades:
        return
    t = trades[0]
    print(f"Trade: {t.trade_type} {t.base_amount} @ {t.price}")

task = asyncio.create_task(sdk.subscribe_my_trades(on_trades))
```

#### Subscribe to Live Market Trades

```python
async def on_market(trades):
    for t in trades:
        arrow = "▲" if t.trade_type == "buy" else "▼"
        print(f"{arrow} {t.price} | {t.base_amount} BNB")

task = asyncio.create_task(
    sdk.subscribe_live_trades("BNB_USDT", on_market, limit=20)
)
```

#### Subscribe to Locked Escrow

```python
async def on_locked(assets):
    for a in assets:
        print(f"Locked: {a.locked_human} {a.token_symbol}")

task = asyncio.create_task(sdk.subscribe_locked_assets(on_locked))
```

---

### On-chain Events

On-chain event listeners arrive **faster** than Hasura (~1-3 second indexing delay).
They run in a background daemon thread and return a stop function.

#### `sdk.on_order_placed(callback)`

```python
def on_placed(order_id: str, tx_hash: str):
    print("Order placed:", order_id)

stop = sdk.on_order_placed(on_placed)
# ... later ...
stop()  # stop listening
```

#### `sdk.on_order_matched(callback)`

```python
def on_matched(ask_order_id: str, bid_order_id: str, tx_hash: str):
    print("Match occurred!")
    print("ASK:", ask_order_id)
    print("BID:", bid_order_id)

stop = sdk.on_order_matched(on_matched)
```

#### `sdk.on_order_cancelled(callback)`

```python
def on_cancelled(order_id: str, tx_hash: str):
    print("Order cancelled:", order_id)

stop = sdk.on_order_cancelled(on_cancelled)
```

---

### Utilities

#### `sdk.get_remaining(order_id) -> str`

Get the unfilled remaining amount of an order (human-readable).

```python
remaining = sdk.get_remaining("0x1a2b...")
print("Remaining:", remaining, "BNB")
```

#### `sdk.is_paused() -> bool`

Check whether the DEX contract is paused.

```python
if sdk.is_paused():
    print("DEX is under maintenance")
```

#### `await sdk.place_ask_token_and_wait(params, timeout_seconds=60.0)`

Place an ERC20 sell order and wait until FILLED.

```python
result, order = await sdk.place_ask_token_and_wait(
    PlaceAskTokenParams(
        base_token  = "0x...",
        quote_token = "0x...",
        price       = 312.50,
        amount      = 1.0,
    ),
    timeout_seconds = 120.0,
)
print("Order filled! Status:", order.status)
```

#### `await sdk.place_bid_and_wait(params, timeout_seconds=60.0)`

```python
result, order = await sdk.place_bid_and_wait(
    PlaceBidParams(base_token="0x...", quote_token="0x...", price=308.00, amount=1.0)
)
```

---

## Types

### `PlaceAskTokenParams`

```python
@dataclass
class PlaceAskTokenParams:
    base_token:  str            # contract address of the token to sell
    quote_token: str            # contract address of the token to receive
    price:       float | str    # human-readable price
    amount:      float | str    # human-readable amount
    expires_at:  int | None     # unix timestamp, default = now + DEFAULT_EXPIRY
```

### `PlaceAskNativeParams`

```python
@dataclass
class PlaceAskNativeParams:
    quote_token: str
    price:       float | str
    amount:      float | str    # amount of BNB to sell
    expires_at:  int | None
```

### `PlaceBidParams`

```python
@dataclass
class PlaceBidParams:
    base_token:  str            # token to buy
    quote_token: str            # token used for payment
    price:       float | str
    amount:      float | str    # amount of base token to buy
    expires_at:  int | None
```

### `Order`

```python
@dataclass
class Order:
    order_id:      str          # format "0x..."
    trader:        str          # lowercase wallet address
    side:          str          # "ASK" | "BID"
    status:        str          # "OPEN" | "PARTIAL" | "FILLED" | "CANCELLED"
    pair_symbol:   str          # e.g. "BNB_USDT"
    price:         str          # human-readable
    amount:        str          # human-readable
    base_filled:   str          # amount filled so far
    quote_filled:  str
    placed_at:     str | None   # ISO timestamp
    updated_at:    str
    tx_hash:       str
    cancelled_tx:  str | None
```

### `PaginatedResult`

```python
@dataclass
class PaginatedResult:
    data:          list         # list of Order or Trade objects
    total_count:   int
    has_next_page: bool
```

---

## Full Examples

### Simple Market Making Bot

See [`examples/simple_bot.py`](examples/simple_bot.py) for a complete bot that:
- Reads market price from the Hasura ticker
- Places an ASK above market price and a BID below it
- Automatically re-places orders when they are filled
- Cancels stale orders when price drifts >1%
- Graceful Ctrl+C shutdown that cancels all active orders

```bash
PRIVATE_KEY=0x... python examples/simple_bot.py
```

### Real-time Monitor

See [`examples/monitor_orders.py`](examples/monitor_orders.py) for:
- Open order monitoring via WebSocket
- Incoming trade feed
- Locked escrow updates
- Live market trade feed
- On-chain event listeners

```bash
PRIVATE_KEY=0x... python examples/monitor_orders.py
```

---

## Running Examples

### 1. Set up the environment

```bash
# In the sdk/python folder
echo "PRIVATE_KEY=0x..." > .env
```

Or export directly:
```bash
export PRIVATE_KEY=0xyour_private_key_here
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run an example

```bash
# Place an order and monitor status
python examples/place_order.py

# Monitor all activity in real-time
python examples/monitor_orders.py

# Run the market making bot
python examples/simple_bot.py
```

### 4. Use in your own project

```python
# Install (after pip install -e . or building the package)
from ordora_sdk import OrdoraSDK, PlaceAskNativeParams
```

Or for development, add the path manually:
```python
import sys
sys.path.insert(0, "sdk/python/src")
from ordora_sdk import OrdoraSDK
```

---

## Security

**Never do this:**
```python
# ❌ WRONG — private key hardcoded in source code
sdk = OrdoraSDK(private_key="0xyourprivatekey...")

# ❌ WRONG — committing a .env file to git
```

**Do this instead:**
```python
# ✅ CORRECT — read from environment variable
import os
sdk = OrdoraSDK(private_key=os.environ["PRIVATE_KEY"])

# ✅ CORRECT — add .env to .gitignore
```

**Additional security notes:**
- The SDK never sends your private key to any server
- Token approvals are made to the DEX contract only (no third parties)
- All transactions are signed locally before being sent to the RPC

---

## Error Reference

### Errors from the DEX Contract

| Error | Cause | Fix |
|---|---|---|
| `MarketNotFound` | Token pair does not exist | Check `base_token` and `quote_token` against `get_markets()` |
| `MarketNotActive` | Market has been deactivated | Wait for the market to be re-enabled |
| `AmountBelowMinimum` | Amount is below the market minimum | Check `min_base_amount` from `get_markets()` |
| `OrderValueBelowMinimum` | Order value (price × amount) is too small | Increase price or amount |
| `InsufficientEscrow` | Insufficient balance to cover escrow | Add funds or reduce the amount |
| `NotYourOrder` | Attempting to cancel another wallet's order | Only your own orders can be cancelled |
| `ExpiryInPast` | `expires_at` is in the past | Use a future Unix timestamp |
| `EnforcedPause` | Contract is paused | Check `sdk.is_paused()` before placing orders |

### SDK / Network Errors

```python
try:
    result = sdk.place_ask_native(PlaceAskNativeParams(...))
except ValueError as e:
    print("Validation error:", e)      # e.g. "Market is not active"
except Exception as e:
    if "insufficient funds" in str(e):
        print("Insufficient BNB for gas + escrow")
    else:
        print("Unknown error:", e)
```

### Subscription Errors

```python
async def on_error(exc: Exception):
    print("WebSocket error:", exc)

task = asyncio.create_task(
    sdk.subscribe_open_orders(on_data, on_error=on_error)
)
```

---

## File Structure

```
sdk/python/
├── README.md
├── pyproject.toml
├── requirements.txt
├── src/
│   └── ordora_sdk/
│       ├── __init__.py    — public exports
│       ├── sdk.py         — OrdoraSDK main class
│       ├── contract.py    — on-chain interaction via web3.py
│       ├── hasura.py      — Hasura GraphQL queries & subscriptions
│       ├── types.py       — all dataclasses & type definitions
│       ├── abi.py         — DEX contract ABI
│       └── constants.py   — chain configs, addresses, ERC20 ABI
└── examples/
    ├── place_order.py     — example: place ASK + BID + monitor status
    ├── monitor_orders.py  — monitor all activity in real-time
    └── simple_bot.py      — complete market making bot
```
