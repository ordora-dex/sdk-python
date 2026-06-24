from __future__ import annotations

import asyncio
from typing import Callable, Optional

from .constants import CHAIN_CONFIGS, HASURA_HTTP_URL, HASURA_WS_URL
from .contract import ContractClient
from .hasura import HasuraClient
from .types import (
    ApprovalResult,
    ChainConfig,
    LockedAsset,
    Market,
    OnChainOrder,
    Order,
    PaginatedResult,
    PlaceAskNativeParams,
    PlaceAskTokenParams,
    PlaceBidParams,
    PlaceOrderResult,
    Ticker,
    Token,
    Trade,
)


class OrdoraSDK:
    """
    Main entry point for the Ordora DEX Python SDK.

    All on-chain methods are synchronous (blocking).
    All Hasura query methods are async coroutines — use ``asyncio.run()`` or
    ``await`` them inside an async context.

    Example::

        sdk = OrdoraSDK(private_key=os.environ["PRIVATE_KEY"])
        result = sdk.place_ask_native(PlaceAskNativeParams(
            quote_token="0xUSDT...",
            price=310.0,
            amount=0.01,
        ))

        import asyncio
        markets = asyncio.run(sdk.get_markets())
    """

    def __init__(
        self,
        private_key: str,
        chain: str | ChainConfig = "bsc-testnet",
        hasura_url: Optional[str] = None,
        hasura_ws_url: Optional[str] = None,
    ) -> None:
        if isinstance(chain, str):
            cfg = CHAIN_CONFIGS.get(chain)
            if cfg is None:
                raise ValueError(f"Unknown chain: {chain!r}")
            self._chain_cfg = cfg
        else:
            self._chain_cfg = chain

        http_url = hasura_url    or HASURA_HTTP_URL
        ws_url   = hasura_ws_url or HASURA_WS_URL

        self._contract = ContractClient(private_key, self._chain_cfg)
        self._hasura   = HasuraClient(http_url, ws_url)

    @property
    def address(self) -> str:
        """Active trader wallet address."""
        return self._contract.address

    @property
    def chain(self) -> ChainConfig:
        """Current chain configuration."""
        return self._chain_cfg

    # ─── Balance ──────────────────────────────────────────────────────────────

    def get_bnb_balance(self) -> int:
        """Get the native BNB balance in wei."""
        return self._contract.get_bnb_balance()

    def get_token_balance(self, token_address: str) -> int:
        """Get the ERC20 token balance in wei."""
        return self._contract.get_token_balance(token_address)

    # ─── Approve ──────────────────────────────────────────────────────────────

    def approve_token(self, token_address: str) -> ApprovalResult:
        """
        Approve an ERC20 token for the DEX contract (unlimited).
        Not required to call manually — place order calls this automatically if needed.
        """
        return self._contract.approve_token(token_address)

    # ─── Place Orders ─────────────────────────────────────────────────────────

    def place_ask_token(self, params: PlaceAskTokenParams) -> PlaceOrderResult:
        """
        Place a SELL order for an ERC20 token.
        Auto-approves the token and encodes price/amount to raw units.

        Example::

            result = sdk.place_ask_token(PlaceAskTokenParams(
                base_token  = "0xToken...",
                quote_token = "0xUSDT...",
                price       = 312.50,
                amount      = 1.5,
            ))
        """
        return self._contract.place_ask_token(params)

    def place_ask_native(self, params: PlaceAskNativeParams) -> PlaceOrderResult:
        """
        Place a SELL order for native BNB.
        BNB is sent as msg.value to the contract — no approval needed.

        Example::

            result = sdk.place_ask_native(PlaceAskNativeParams(
                quote_token = "0xUSDT...",
                price       = 312.50,
                amount      = 0.5,
            ))
        """
        return self._contract.place_ask_native(params)

    def place_bid(self, params: PlaceBidParams) -> PlaceOrderResult:
        """
        Place a BUY order for a token.
        Auto-approves the quote token or sends BNB if native.

        Example::

            result = sdk.place_bid(PlaceBidParams(
                base_token  = "0xToken...",
                quote_token = "0xUSDT...",
                price       = 310.00,
                amount      = 2.0,
            ))
        """
        return self._contract.place_bid(params)

    # ─── Cancel ───────────────────────────────────────────────────────────────

    def cancel_order(self, order_id: str) -> str:
        """
        Cancel your own order.
        Escrowed funds are returned to the wallet after a successful cancel.
        Returns the transaction hash.
        """
        return self._contract.cancel_order(order_id)

    # ─── On-chain Read ────────────────────────────────────────────────────────

    def get_order_on_chain(self, order_id: str) -> OnChainOrder:
        """Fetch order details directly from the blockchain (accurate, but slower than Hasura)."""
        return self._contract.get_order_on_chain(order_id)

    def get_remaining(self, order_id: str) -> str:
        """Get the unfilled remaining amount for an order (human-readable)."""
        return self._contract.get_remaining(order_id)

    def is_paused(self) -> bool:
        """Check whether the DEX contract is paused."""
        return self._contract.is_paused()

    # ─── Hasura: Orders ───────────────────────────────────────────────────────

    async def get_open_orders(self) -> list[Order]:
        """Fetch all open orders for this wallet (status OPEN or PARTIAL)."""
        return await self._hasura.get_open_orders(self.address)

    async def get_order_history(
        self, limit: int = 50, offset: int = 0
    ) -> PaginatedResult:
        """Fetch the full order history for this wallet (all statuses)."""
        return await self._hasura.get_order_history(self.address, limit, offset)

    async def get_order_by_id(self, order_id: str) -> Optional[Order]:
        """
        Fetch a single order by ID from Hasura.
        Faster than on-chain, but subject to ~1-3 second indexing delay.
        """
        return await self._hasura.get_order_by_id(order_id)

    # ─── Hasura: Trades ───────────────────────────────────────────────────────

    async def get_my_trades(
        self, limit: int = 50, offset: int = 0
    ) -> PaginatedResult:
        """Fetch trade history for this wallet (as seller or buyer)."""
        return await self._hasura.get_my_trades(self.address, limit, offset)

    async def get_trades_by_pair(self, pair: str, limit: int = 50) -> list[Trade]:
        """Fetch trade history for a trading pair."""
        return await self._hasura.get_trades_by_pair(pair, limit)

    async def get_trades_by_order(self, order_id: str) -> list[Trade]:
        """Fetch all trades that filled a specific order."""
        return await self._hasura.get_trades_by_order(order_id)

    # ─── Hasura: Market & Ticker ──────────────────────────────────────────────

    async def get_markets(self) -> list[Market]:
        """Fetch all active markets."""
        return await self._hasura.get_markets()

    async def get_all_tickers(self) -> list[Ticker]:
        """Fetch tickers for all markets."""
        return await self._hasura.get_all_tickers()

    async def get_ticker(self, pair: str) -> Optional[Ticker]:
        """Fetch the ticker for a specific pair."""
        return await self._hasura.get_ticker(pair)

    # ─── Hasura: Assets ───────────────────────────────────────────────────────

    async def get_tokens(self) -> list[Token]:
        """Fetch available tokens."""
        return await self._hasura.get_tokens()

    async def get_locked_assets(self) -> list[LockedAsset]:
        """Fetch assets currently locked in escrow."""
        return await self._hasura.get_locked_assets(self.address)

    # ─── Subscriptions ────────────────────────────────────────────────────────

    async def subscribe_open_orders(
        self,
        on_data: Callable[[list[Order]], None],
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """
        Subscribe to open orders for this wallet (real-time via WebSocket).
        Runs until the task is cancelled.

        Example::

            async def handler(orders):
                print(f"{len(orders)} open order(s)")

            task = asyncio.create_task(sdk.subscribe_open_orders(handler))
            await asyncio.sleep(60)
            task.cancel()
        """
        await self._hasura.subscribe_open_orders(self.address, on_data, on_error)

    async def subscribe_order_status(
        self,
        order_id: str,
        on_data: Callable[[Optional[Order]], None],
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """
        Subscribe to a single order's status (real-time via WebSocket).
        Useful for waiting for confirmation after placing an order.
        """
        await self._hasura.subscribe_order_status(order_id, on_data, on_error)

    async def subscribe_my_trades(
        self,
        on_data: Callable[[list[Trade]], None],
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Subscribe to incoming trades for this wallet in real-time."""
        await self._hasura.subscribe_my_trades(self.address, on_data, on_error)

    async def subscribe_live_trades(
        self,
        pair: str,
        on_data: Callable[[list[Trade]], None],
        limit: int = 30,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Subscribe to live trades for a trading pair."""
        await self._hasura.subscribe_live_trades(pair, on_data, limit, on_error)

    async def subscribe_locked_assets(
        self,
        on_data: Callable[[list[LockedAsset]], None],
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Subscribe to locked assets (live updates when orders are filled or cancelled)."""
        await self._hasura.subscribe_locked_assets(self.address, on_data, on_error)

    # ─── On-chain Event Listeners ─────────────────────────────────────────────

    def on_order_placed(
        self,
        callback: Callable[[str, str], None],
        poll_interval: float = 2.0,
    ) -> Callable[[], None]:
        """
        Listen for OrderPlaced on-chain events for this wallet.
        Returns a stop function — call it to unsubscribe.
        Fires before the Hasura indexer records the order.
        """
        return self._contract.on_order_placed(callback, poll_interval)

    def on_order_matched(
        self,
        callback: Callable[[str, str, str], None],
        poll_interval: float = 2.0,
    ) -> Callable[[], None]:
        """
        Listen for OrderMatched on-chain events involving this wallet.
        Returns a stop function.
        """
        return self._contract.on_order_matched(callback, poll_interval)

    def on_order_cancelled(
        self,
        callback: Callable[[str, str], None],
        poll_interval: float = 2.0,
    ) -> Callable[[], None]:
        """
        Listen for OrderCancelled on-chain events for this wallet.
        Returns a stop function.
        """
        return self._contract.on_order_cancelled(callback, poll_interval)

    # ─── Utilities ────────────────────────────────────────────────────────────

    async def place_ask_token_and_wait(
        self,
        params: PlaceAskTokenParams,
        timeout_seconds: float = 60.0,
    ) -> tuple[PlaceOrderResult, Order]:
        """
        Place an ERC20 sell order and wait until it is FILLED.
        Returns (PlaceOrderResult, Order).
        Raises TimeoutError if not filled within timeout_seconds.
        """
        result = self.place_ask_token(params)
        order  = await self._hasura.wait_for_order_status(
            result.order_id, "FILLED", timeout_seconds
        )
        return result, order

    async def place_bid_and_wait(
        self,
        params: PlaceBidParams,
        timeout_seconds: float = 60.0,
    ) -> tuple[PlaceOrderResult, Order]:
        """
        Place a buy order and wait until it is FILLED.
        Returns (PlaceOrderResult, Order).
        Raises TimeoutError if not filled within timeout_seconds.
        """
        result = self.place_bid(params)
        order  = await self._hasura.wait_for_order_status(
            result.order_id, "FILLED", timeout_seconds
        )
        return result, order
