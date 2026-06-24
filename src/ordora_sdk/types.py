from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ─── Enums ────────────────────────────────────────────────────────────────────

OrderSide   = str  # "ASK" | "BID"
OrderStatus = str  # "OPEN" | "PARTIAL" | "FILLED" | "CANCELLED"
TradeType   = str  # "buy" | "sell"


# ─── Hasura Response Types ────────────────────────────────────────────────────

@dataclass
class Market:
    """Market data from Hasura."""
    market_id:        str
    pair_symbol:      str
    base_token:       str
    quote_token:      str
    base_decimals:    int
    quote_decimals:   int
    price_precision:  int
    amount_precision: int
    min_base_amount:  str
    min_quote_amount: str
    active:           bool

    @staticmethod
    def from_dict(d: dict) -> "Market":
        return Market(
            market_id        = d["market_id"],
            pair_symbol      = d["pair_symbol"],
            base_token       = d["base_token"],
            quote_token      = d["quote_token"],
            base_decimals    = int(d["base_decimals"]),
            quote_decimals   = int(d["quote_decimals"]),
            price_precision  = int(d["price_precision"]),
            amount_precision = int(d["amount_precision"]),
            min_base_amount  = d["min_base_amount"],
            min_quote_amount = d["min_quote_amount"],
            active           = bool(d["active"]),
        )


@dataclass
class Order:
    """Order from Hasura (human-readable values)."""
    order_id:      str
    trader:        str
    side:          OrderSide
    status:        OrderStatus
    pair_symbol:   str
    market_id:     str
    base_token:    str
    quote_token:   str
    price:         str
    amount:        str
    base_filled:   str
    quote_filled:  str
    escrow_token:  Optional[str]
    escrow_amount: Optional[str]
    expires_at:    Optional[str]
    placed_at:     Optional[str]
    updated_at:    str
    tx_hash:       str
    placed_tx:     str
    cancelled_tx:  Optional[str]

    @staticmethod
    def from_dict(d: dict) -> "Order":
        return Order(
            order_id      = d["order_id"],
            trader        = d["trader"],
            side          = d["side"],
            status        = d["status"],
            pair_symbol   = d["pair_symbol"],
            market_id     = d["market_id"],
            base_token    = d["base_token"],
            quote_token   = d["quote_token"],
            price         = str(d["price"]),
            amount        = str(d["amount"]),
            base_filled   = str(d["base_filled"]),
            quote_filled  = str(d["quote_filled"]),
            escrow_token  = d.get("escrow_token"),
            escrow_amount = d.get("escrow_amount"),
            expires_at    = d.get("expires_at"),
            placed_at     = d.get("placed_at"),
            updated_at    = d["updated_at"],
            tx_hash       = d.get("tx_hash", ""),
            placed_tx     = d.get("placed_tx", ""),
            cancelled_tx  = d.get("cancelled_tx"),
        )


@dataclass
class Trade:
    """Trade from Hasura (human-readable values)."""
    id:           str
    pair_symbol:  str
    market_id:    str
    price:        str
    base_amount:  str
    quote_amount: str
    trade_type:   TradeType
    tx_hash:      str
    traded_at:    str
    ask_trader:   str
    bid_trader:   str
    ask_order_id: str
    bid_order_id: str

    @staticmethod
    def from_dict(d: dict) -> "Trade":
        return Trade(
            id           = d["id"],
            pair_symbol  = d["pair_symbol"],
            market_id    = d.get("market_id", ""),
            price        = str(d["price"]),
            base_amount  = str(d["base_amount"]),
            quote_amount = str(d.get("quote_amount", "0")),
            trade_type   = d["trade_type"],
            tx_hash      = d.get("tx_hash", ""),
            traded_at    = d["traded_at"],
            ask_trader   = d.get("ask_trader", ""),
            bid_trader   = d.get("bid_trader", ""),
            ask_order_id = d.get("ask_order_id", ""),
            bid_order_id = d.get("bid_order_id", ""),
        )


@dataclass
class Ticker:
    """24-hour ticker from Hasura."""
    pair_symbol:          str
    market_id:            str
    last_price:           str
    open_24h:             str
    high_24h:             str
    low_24h:              str
    price_change_pct_24h: str
    base_volume_24h:      str
    quote_volume_24h:     str
    trade_count_24h:      int
    highest_bid:          str
    lowest_ask:           str
    liquidity_in_usd:     str
    is_frozen:            bool
    updated_at:           str

    @staticmethod
    def from_dict(d: dict) -> "Ticker":
        def _str(v) -> str:
            return "0" if v is None else str(v)

        return Ticker(
            pair_symbol          = d["pair_symbol"],
            market_id            = d.get("market_id", ""),
            last_price           = _str(d.get("last_price")),
            open_24h             = _str(d.get("open_24h")),
            high_24h             = _str(d.get("high_24h")),
            low_24h              = _str(d.get("low_24h")),
            price_change_pct_24h = _str(d.get("price_change_pct_24h")),
            base_volume_24h      = _str(d.get("base_volume_24h")),
            quote_volume_24h     = _str(d.get("quote_volume_24h")),
            trade_count_24h      = int(d.get("trade_count_24h") or 0),
            highest_bid          = _str(d.get("highest_bid")),
            lowest_ask           = _str(d.get("lowest_ask")),
            liquidity_in_usd     = _str(d.get("liquidity_in_usd")),
            is_frozen            = bool(d.get("is_frozen", False)),
            updated_at           = d.get("updated_at", ""),
        )


@dataclass
class Token:
    """Token from Hasura."""
    address:      str
    symbol:       str
    name:         str
    decimals:     int
    icon_url:     str
    usd_price:    str
    can_deposit:  bool
    can_withdraw: bool
    active:       bool

    @staticmethod
    def from_dict(d: dict) -> "Token":
        return Token(
            address      = d["address"],
            symbol       = d["symbol"],
            name         = d["name"],
            decimals     = int(d["decimals"]),
            icon_url     = d.get("icon_url", ""),
            usd_price    = str(d.get("usd_price", "0")),
            can_deposit  = bool(d.get("can_deposit", False)),
            can_withdraw = bool(d.get("can_withdraw", False)),
            active       = bool(d["active"]),
        )


@dataclass
class LockedAsset:
    """Locked asset from Hasura."""
    token_address:  str
    token_symbol:   str
    token_decimals: int
    locked_human:   str
    order_count:    int

    @staticmethod
    def from_dict(d: dict) -> "LockedAsset":
        return LockedAsset(
            token_address  = d["token_address"],
            token_symbol   = d["token_symbol"],
            token_decimals = int(d["token_decimals"]),
            locked_human   = str(d["locked_human"]),
            order_count    = int(d["order_count"]),
        )


@dataclass
class OnChainOrder:
    """On-chain order data (from contract.getOrder)."""
    trader:        str
    side:          int   # 0 = ASK, 1 = BID
    status:        int   # 0 = OPEN, 1 = PARTIAL, 2 = FILLED, 3 = CANCELLED
    base_decimals: int
    base_token:    str
    expires_at:    int
    placed_at:     int
    quote_token:   str
    price:         int
    amount:        int
    filled:        int
    base_filled:   int
    escrow_amount: int


# ─── Parameter Types ─────────────────────────────────────────────────────────

@dataclass
class PlaceAskTokenParams:
    """Parameters for placing an ERC20 sell order."""
    base_token:  str
    quote_token: str
    price:       float | str
    amount:      float | str
    expires_at:  Optional[int] = None


@dataclass
class PlaceAskNativeParams:
    """Parameters for placing a native BNB sell order."""
    quote_token: str
    price:       float | str
    amount:      float | str
    expires_at:  Optional[int] = None


@dataclass
class PlaceBidParams:
    """Parameters for placing a buy order."""
    base_token:  str
    quote_token: str
    price:       float | str
    amount:      float | str
    expires_at:  Optional[int] = None


# ─── Result Types ─────────────────────────────────────────────────────────────

@dataclass
class PlaceOrderResult:
    """Result returned after placing an order."""
    order_id: str   # Order ID for status tracking (0x...)
    tx_hash:  str   # Transaction hash


@dataclass
class ApprovalResult:
    """Result returned after an ERC20 approval."""
    approved: bool            # True if approval was submitted
    tx_hash:  Optional[str] = None


# ─── Config Types ─────────────────────────────────────────────────────────────

@dataclass
class ChainConfig:
    """On-chain configuration for a supported network."""
    chain_id:         int
    rpc_url:          str
    contract_address: str
    wbnb_address:     str
    explorer_url:     str


# ─── Pagination ───────────────────────────────────────────────────────────────

@dataclass
class PaginatedResult:
    """Paginated response from Hasura."""
    data:         list
    total_count:  int
    has_next_page: bool
