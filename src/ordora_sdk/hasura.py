from __future__ import annotations

import asyncio
import inspect
from typing import AsyncGenerator, Callable, Optional

import aiohttp
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.websockets import WebsocketsTransport

from .types import (
    LockedAsset,
    Market,
    Order,
    PaginatedResult,
    Ticker,
    Token,
    Trade,
)


# ─── GraphQL Queries ──────────────────────────────────────────────────────────

_Q_MARKETS = gql("""
  query Markets {
    markets_view(
      where: { active: { _eq: true } }
      order_by: { pair_symbol: asc }
    ) {
      market_id pair_symbol base_token quote_token
      base_decimals quote_decimals price_precision amount_precision
      min_base_amount min_quote_amount active
    }
  }
""")

_Q_OPEN_ORDERS = gql("""
  query OpenOrders($wallet: String!) {
    orders_view(
      where: {
        trader: { _eq: $wallet }
        status: { _in: ["OPEN", "PARTIAL"] }
      }
      order_by: { placed_at: desc }
    ) {
      order_id trader side status pair_symbol market_id
      base_token quote_token price amount base_filled quote_filled
      escrow_token escrow_amount expires_at placed_at updated_at
      tx_hash placed_tx cancelled_tx
    }
  }
""")

_Q_ORDER_HISTORY = gql("""
  query OrderHistory($wallet: String!, $limit: Int!, $offset: Int!) {
    orders_view_aggregate(where: { trader: { _eq: $wallet } }) {
      aggregate { count }
    }
    orders_view(
      where: { trader: { _eq: $wallet } }
      order_by: { placed_at: desc }
      limit: $limit
      offset: $offset
    ) {
      order_id trader side status pair_symbol market_id
      base_token quote_token price amount base_filled quote_filled
      escrow_token escrow_amount expires_at placed_at updated_at
      tx_hash placed_tx cancelled_tx
    }
  }
""")

_Q_ORDER_BY_ID = gql("""
  query OrderById($orderId: String!) {
    orders_view(
      where: { order_id: { _eq: $orderId } }
      limit: 1
    ) {
      order_id trader side status pair_symbol market_id
      base_token quote_token price amount base_filled quote_filled
      escrow_token escrow_amount expires_at placed_at updated_at
      tx_hash placed_tx cancelled_tx
    }
  }
""")

_Q_MY_TRADES = gql("""
  query MyTrades($wallet: String!, $limit: Int!, $offset: Int!) {
    trades_view_aggregate(
      where: {
        _or: [
          { ask_trader: { _eq: $wallet } }
          { bid_trader: { _eq: $wallet } }
        ]
      }
    ) {
      aggregate { count }
    }
    trades_view(
      where: {
        _or: [
          { ask_trader: { _eq: $wallet } }
          { bid_trader: { _eq: $wallet } }
        ]
      }
      order_by: { traded_at: desc }
      limit: $limit
      offset: $offset
    ) {
      id pair_symbol market_id price base_amount quote_amount
      trade_type tx_hash traded_at ask_trader bid_trader
      ask_order_id bid_order_id
    }
  }
""")

_Q_TRADES_BY_PAIR = gql("""
  query TradesByPair($pair: String!, $limit: Int!) {
    trades_view(
      where: { pair_symbol: { _eq: $pair } }
      order_by: { traded_at: desc }
      limit: $limit
    ) {
      id pair_symbol price base_amount quote_amount
      trade_type tx_hash traded_at ask_trader bid_trader
    }
  }
""")

_Q_TRADES_BY_ORDER = gql("""
  query TradesByOrder($orderId: String!) {
    trades_view(
      where: {
        _or: [
          { ask_order_id: { _eq: $orderId } }
          { bid_order_id: { _eq: $orderId } }
        ]
      }
      order_by: { traded_at: asc }
    ) {
      id price base_amount quote_amount trade_type traded_at tx_hash
    }
  }
""")

_Q_TICKER_ALL = gql("""
  query AllTickers {
    ticker_full(
      where: { is_frozen: { _eq: false } }
      order_by: { quote_volume_24h: desc }
    ) {
      pair_symbol market_id last_price open_24h high_24h low_24h
      price_change_pct_24h base_volume_24h quote_volume_24h trade_count_24h
      highest_bid lowest_ask liquidity_in_usd is_frozen updated_at
    }
  }
""")

_Q_TICKER_ONE = gql("""
  query Ticker($pair: String!) {
    ticker_full(
      where: { pair_symbol: { _eq: $pair } }
      limit: 1
    ) {
      pair_symbol market_id last_price open_24h high_24h low_24h
      price_change_pct_24h base_volume_24h quote_volume_24h trade_count_24h
      highest_bid lowest_ask liquidity_in_usd is_frozen updated_at
    }
  }
""")

_Q_LOCKED_ASSETS = gql("""
  query LockedAssets($wallet: String!) {
    locked_assets(where: { trader: { _eq: $wallet } }) {
      token_address token_symbol token_decimals locked_human order_count
    }
  }
""")

_Q_TOKENS = gql("""
  query Tokens {
    token_registry(
      where: { active: { _eq: true } }
      order_by: { position: asc }
    ) {
      address symbol name decimals icon_url usd_price
      can_deposit can_withdraw active
    }
  }
""")

# ─── GraphQL Subscriptions ────────────────────────────────────────────────────

_SUB_OPEN_ORDERS = """
  subscription OpenOrdersLive($wallet: String!) {
    orders_view(
      where: {
        trader: { _eq: $wallet }
        status: { _in: ["OPEN", "PARTIAL"] }
      }
      order_by: { placed_at: desc }
    ) {
      order_id trader side status pair_symbol market_id
      base_token quote_token price amount base_filled quote_filled
      escrow_token escrow_amount expires_at placed_at updated_at
      tx_hash placed_tx cancelled_tx
    }
  }
"""

_SUB_ORDER_STATUS = """
  subscription OrderStatusLive($orderId: String!) {
    orders_view(
      where: { order_id: { _eq: $orderId } }
      limit: 1
    ) {
      order_id trader side status pair_symbol market_id
      base_token quote_token price amount base_filled quote_filled
      escrow_token escrow_amount expires_at placed_at updated_at
      tx_hash placed_tx cancelled_tx
    }
  }
"""

_SUB_LIVE_TRADES = """
  subscription LiveTrades($pair: String!, $limit: Int!) {
    trades_view(
      where: { pair_symbol: { _eq: $pair } }
      order_by: { traded_at: desc }
      limit: $limit
    ) {
      id pair_symbol price base_amount trade_type traded_at tx_hash
    }
  }
"""

_SUB_MY_TRADES = """
  subscription MyTradesLive($wallet: String!) {
    trades_view(
      where: {
        _or: [
          { ask_trader: { _eq: $wallet } }
          { bid_trader: { _eq: $wallet } }
        ]
      }
      order_by: { traded_at: desc }
      limit: 20
    ) {
      id pair_symbol price base_amount trade_type traded_at
    }
  }
"""

_SUB_LOCKED_ASSETS = """
  subscription LockedAssetsLive($wallet: String!) {
    locked_assets(where: { trader: { _eq: $wallet } }) {
      token_symbol locked_human order_count
    }
  }
"""


async def _call(fn: Callable, *args) -> None:
    """Call fn(*args), awaiting if it returns a coroutine."""
    result = fn(*args)
    if inspect.isawaitable(result):
        await result


# ─── HasuraClient ─────────────────────────────────────────────────────────────

class HasuraClient:
    """Async client for Hasura GraphQL queries and WebSocket subscriptions."""

    def __init__(self, http_url: str, ws_url: str) -> None:
        self._http_url = http_url
        self._ws_url   = ws_url

    def _http_client(self) -> Client:
        transport = AIOHTTPTransport(url=self._http_url)
        return Client(transport=transport, fetch_schema_from_transport=False)

    # ─── Markets ──────────────────────────────────────────────────────────────

    async def get_markets(self) -> list[Market]:
        async with self._http_client() as session:
            result = await session.execute(_Q_MARKETS)
        return [Market.from_dict(d) for d in result["markets_view"]]

    # ─── Orders ───────────────────────────────────────────────────────────────

    async def get_open_orders(self, wallet: str) -> list[Order]:
        async with self._http_client() as session:
            result = await session.execute(
                _Q_OPEN_ORDERS, variable_values={"wallet": wallet.lower()}
            )
        return [Order.from_dict(d) for d in result["orders_view"]]

    async def get_order_history(
        self,
        wallet: str,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResult:
        async with self._http_client() as session:
            result = await session.execute(
                _Q_ORDER_HISTORY,
                variable_values={"wallet": wallet.lower(), "limit": limit, "offset": offset},
            )
        total = result["orders_view_aggregate"]["aggregate"]["count"]
        data  = [Order.from_dict(d) for d in result["orders_view"]]
        return PaginatedResult(
            data          = data,
            total_count   = total,
            has_next_page = offset + limit < total,
        )

    async def get_order_by_id(self, order_id: str) -> Optional[Order]:
        async with self._http_client() as session:
            result = await session.execute(
                _Q_ORDER_BY_ID, variable_values={"orderId": order_id}
            )
        rows = result["orders_view"]
        return Order.from_dict(rows[0]) if rows else None

    # ─── Trades ───────────────────────────────────────────────────────────────

    async def get_my_trades(
        self,
        wallet: str,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResult:
        async with self._http_client() as session:
            result = await session.execute(
                _Q_MY_TRADES,
                variable_values={"wallet": wallet.lower(), "limit": limit, "offset": offset},
            )
        total = result["trades_view_aggregate"]["aggregate"]["count"]
        data  = [Trade.from_dict(d) for d in result["trades_view"]]
        return PaginatedResult(
            data          = data,
            total_count   = total,
            has_next_page = offset + limit < total,
        )

    async def get_trades_by_pair(self, pair: str, limit: int = 50) -> list[Trade]:
        async with self._http_client() as session:
            result = await session.execute(
                _Q_TRADES_BY_PAIR, variable_values={"pair": pair, "limit": limit}
            )
        return [Trade.from_dict(d) for d in result["trades_view"]]

    async def get_trades_by_order(self, order_id: str) -> list[Trade]:
        async with self._http_client() as session:
            result = await session.execute(
                _Q_TRADES_BY_ORDER, variable_values={"orderId": order_id}
            )
        return [Trade.from_dict(d) for d in result["trades_view"]]

    # ─── Ticker ───────────────────────────────────────────────────────────────

    async def get_all_tickers(self) -> list[Ticker]:
        async with self._http_client() as session:
            result = await session.execute(_Q_TICKER_ALL)
        return [Ticker.from_dict(d) for d in result["ticker_full"]]

    async def get_ticker(self, pair: str) -> Optional[Ticker]:
        async with self._http_client() as session:
            result = await session.execute(
                _Q_TICKER_ONE, variable_values={"pair": pair}
            )
        rows = result["ticker_full"]
        return Ticker.from_dict(rows[0]) if rows else None

    # ─── Locked Assets ────────────────────────────────────────────────────────

    async def get_locked_assets(self, wallet: str) -> list[LockedAsset]:
        async with self._http_client() as session:
            result = await session.execute(
                _Q_LOCKED_ASSETS, variable_values={"wallet": wallet.lower()}
            )
        return [LockedAsset.from_dict(d) for d in result["locked_assets"]]

    # ─── Tokens ───────────────────────────────────────────────────────────────

    async def get_tokens(self) -> list[Token]:
        async with self._http_client() as session:
            result = await session.execute(_Q_TOKENS)
        return [Token.from_dict(d) for d in result["token_registry"]]

    # ─── Subscriptions ────────────────────────────────────────────────────────

    async def subscribe_open_orders(
        self,
        wallet: str,
        on_data: Callable[[list[Order]], None],
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """
        Subscribe to open orders for a wallet (real-time via WebSocket).
        Runs until the coroutine is cancelled.
        """
        transport = WebsocketsTransport(url=self._ws_url)
        async with Client(transport=transport, fetch_schema_from_transport=False) as session:
            query = gql(_SUB_OPEN_ORDERS)
            try:
                async for result in session.subscribe(
                    query, variable_values={"wallet": wallet.lower()}
                ):
                    orders = [Order.from_dict(d) for d in (result.get("orders_view") or [])]
                    await _call(on_data, orders)
            except Exception as exc:
                if on_error:
                    await _call(on_error, exc)
                else:
                    raise

    async def subscribe_order_status(
        self,
        order_id: str,
        on_data: Callable[[Optional[Order]], None],
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """
        Subscribe to a single order's status (real-time via WebSocket).
        Useful for waiting for FILLED after placing an order.
        """
        transport = WebsocketsTransport(url=self._ws_url)
        async with Client(transport=transport, fetch_schema_from_transport=False) as session:
            query = gql(_SUB_ORDER_STATUS)
            try:
                async for result in session.subscribe(
                    query, variable_values={"orderId": order_id}
                ):
                    rows  = result.get("orders_view") or []
                    order = Order.from_dict(rows[0]) if rows else None
                    await _call(on_data, order)
            except Exception as exc:
                if on_error:
                    await _call(on_error, exc)
                else:
                    raise

    async def subscribe_my_trades(
        self,
        wallet: str,
        on_data: Callable[[list[Trade]], None],
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Subscribe to incoming trades for a wallet in real-time."""
        transport = WebsocketsTransport(url=self._ws_url)
        async with Client(transport=transport, fetch_schema_from_transport=False) as session:
            query = gql(_SUB_MY_TRADES)
            try:
                async for result in session.subscribe(
                    query, variable_values={"wallet": wallet.lower()}
                ):
                    trades = [Trade.from_dict(d) for d in (result.get("trades_view") or [])]
                    await _call(on_data, trades)
            except Exception as exc:
                if on_error:
                    await _call(on_error, exc)
                else:
                    raise

    async def subscribe_live_trades(
        self,
        pair: str,
        on_data: Callable[[list[Trade]], None],
        limit: int = 30,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Subscribe to live trades for a trading pair."""
        transport = WebsocketsTransport(url=self._ws_url)
        async with Client(transport=transport, fetch_schema_from_transport=False) as session:
            query = gql(_SUB_LIVE_TRADES)
            try:
                async for result in session.subscribe(
                    query, variable_values={"pair": pair, "limit": limit}
                ):
                    trades = [Trade.from_dict(d) for d in (result.get("trades_view") or [])]
                    await _call(on_data, trades)
            except Exception as exc:
                if on_error:
                    await _call(on_error, exc)
                else:
                    raise

    async def subscribe_locked_assets(
        self,
        wallet: str,
        on_data: Callable[[list[LockedAsset]], None],
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Subscribe to locked assets (live updates when orders are filled or cancelled)."""
        transport = WebsocketsTransport(url=self._ws_url)
        async with Client(transport=transport, fetch_schema_from_transport=False) as session:
            query = gql(_SUB_LOCKED_ASSETS)
            try:
                async for result in session.subscribe(
                    query, variable_values={"wallet": wallet.lower()}
                ):
                    assets = [
                        LockedAsset.from_dict(d)
                        for d in (result.get("locked_assets") or [])
                    ]
                    await _call(on_data, assets)
            except Exception as exc:
                if on_error:
                    await _call(on_error, exc)
                else:
                    raise

    async def wait_for_order_status(
        self,
        order_id: str,
        target_status: str,
        timeout_seconds: float = 60.0,
    ) -> Order:
        """
        Wait for an order to reach a given status.
        Raises TimeoutError if the target status is not reached within timeout_seconds.
        """
        result: Optional[Order] = None
        event = asyncio.Event()

        async def _on_data(order: Optional[Order]) -> None:
            nonlocal result
            if order and order.status == target_status:
                result = order
                event.set()

        task = asyncio.create_task(self.subscribe_order_status(order_id, _on_data))

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            task.cancel()
            raise TimeoutError(
                f"Timeout waiting for order {order_id} to reach {target_status}"
            )
        finally:
            task.cancel()

        assert result is not None
        return result
