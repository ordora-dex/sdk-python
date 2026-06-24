from __future__ import annotations

import os
import random
import time
from typing import Callable, Optional

from eth_account import Account
from eth_typing import HexStr
from web3 import Web3
from web3.contract import Contract
from web3.types import TxReceipt

from .abi import DEX_ABI
from .constants import ERC20_ABI, NATIVE_ADDRESS, MAX_UINT256
from .types import (
    ApprovalResult,
    ChainConfig,
    OnChainOrder,
    PlaceAskNativeParams,
    PlaceAskTokenParams,
    PlaceBidParams,
    PlaceOrderResult,
)


class ContractClient:
    """Low-level on-chain client wrapping the Ordora DEX contract via web3.py."""

    def __init__(self, private_key: str, chain: ChainConfig) -> None:
        self._chain   = chain
        self._w3      = Web3(Web3.HTTPProvider(chain.rpc_url))
        self._account = Account.from_key(private_key)
        self._dex: Contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(chain.contract_address),
            abi=DEX_ABI,
        )

    @property
    def address(self) -> str:
        return self._account.address

    # ─── Order ID Generation ──────────────────────────────────────────────────

    def generate_nonce(self) -> int:
        """Generate a unique nonce from timestamp + random to avoid collisions."""
        ts   = int(time.time() * 1000)
        rand = random.randint(0, 999_999)
        return ts * 1_000_000 + rand

    def generate_order_id(self, nonce: int) -> bytes:
        """Generate a unique order ID: keccak256(abi.encode(trader, nonce))."""
        encoded = Web3.solidity_keccak(
            ["address", "uint256"],
            [self._account.address, nonce],
        )
        return encoded

    # ─── ERC20 Helpers ────────────────────────────────────────────────────────

    def get_bnb_balance(self) -> int:
        """Get the trader's native BNB balance in wei."""
        return self._w3.eth.get_balance(self._account.address)

    def get_token_balance(self, token_address: str) -> int:
        """Get the trader's ERC20 token balance in wei."""
        token = self._w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=ERC20_ABI,
        )
        return token.functions.balanceOf(self._account.address).call()

    def get_allowance(self, token_address: str) -> int:
        """Get the approved token allowance for the DEX contract."""
        token = self._w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=ERC20_ABI,
        )
        return token.functions.allowance(
            self._account.address,
            self._chain.contract_address,
        ).call()

    def approve_token(
        self,
        token_address: str,
        amount: int = MAX_UINT256,
    ) -> ApprovalResult:
        """
        Approve an ERC20 token for the DEX contract.
        Defaults to unlimited approval so future orders do not require re-approval.
        """
        current = self.get_allowance(token_address)
        if current >= amount:
            return ApprovalResult(approved=False)

        token = self._w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=ERC20_ABI,
        )
        tx   = token.functions.approve(
            Web3.to_checksum_address(self._chain.contract_address),
            MAX_UINT256,
        ).build_transaction(self._base_tx())
        receipt = self._send(tx)
        return ApprovalResult(approved=True, tx_hash=receipt["transactionHash"].hex())

    def _ensure_allowance(self, token_address: str, required: int) -> None:
        """Ensure allowance is sufficient. Auto-approves if below required amount."""
        if self.get_allowance(token_address) < required:
            self.approve_token(token_address)

    # ─── Market Info ──────────────────────────────────────────────────────────

    def get_market_on_chain(self, base_token: str, quote_token: str) -> dict:
        """Fetch market info from the on-chain contract."""
        m = self._dex.functions.getMarket(
            Web3.to_checksum_address(base_token),
            Web3.to_checksum_address(quote_token),
        ).call()
        return {
            "active":           m[0],
            "base_decimals":    m[1],
            "quote_decimals":   m[2],
            "price_precision":  m[3],
            "amount_precision": m[4],
            "min_base_amount":  m[5],
            "min_quote_amount": m[6],
        }

    def is_paused(self) -> bool:
        """Check whether the contract is paused."""
        return self._dex.functions.paused().call()

    def get_default_expiry(self) -> int:
        """Fetch the default order expiry from the contract (in seconds)."""
        return self._dex.functions.DEFAULT_EXPIRY().call()

    # ─── Order Read ───────────────────────────────────────────────────────────

    def get_order_on_chain(self, order_id: str) -> OnChainOrder:
        """Fetch order details from the on-chain contract."""
        order_bytes = bytes.fromhex(order_id.removeprefix("0x"))
        o = self._dex.functions.getOrder(order_bytes).call()
        return OnChainOrder(
            trader        = o[0],
            side          = o[1],
            status        = o[2],
            base_decimals = o[3],
            base_token    = o[4],
            expires_at    = o[5],
            placed_at     = o[6],
            quote_token   = o[7],
            price         = o[8],
            amount        = o[9],
            filled        = o[10],
            base_filled   = o[11],
            escrow_amount = o[12],
        )

    def get_remaining_raw(self, order_id: str) -> int:
        """Fetch the unfilled amount remaining for an order (raw units)."""
        order_bytes = bytes.fromhex(order_id.removeprefix("0x"))
        return self._dex.functions.remaining(order_bytes).call()

    def get_remaining(self, order_id: str) -> str:
        """Fetch the remaining unfilled amount in human-readable form."""
        raw   = self.get_remaining_raw(order_id)
        order = self.get_order_on_chain(order_id)
        return str(raw / 10 ** order.base_decimals)

    # ─── Place ASK (Sell) ─────────────────────────────────────────────────────

    def place_ask_token(self, params: PlaceAskTokenParams) -> PlaceOrderResult:
        """
        Place a sell order for an ERC20 token.
        Auto-fetches market decimals, encodes price/amount to raw units,
        and approves the token if allowance is insufficient.
        """
        market = self.get_market_on_chain(params.base_token, params.quote_token)
        if not market["active"]:
            raise ValueError("Market is not active")

        price_raw  = self._to_raw(params.price,  market["quote_decimals"])
        amount_raw = self._to_raw(params.amount, market["base_decimals"])

        self._ensure_allowance(params.base_token, amount_raw)

        nonce      = self.generate_nonce()
        order_id_b = self.generate_order_id(nonce)
        expires_at = params.expires_at or self._resolve_expiry()

        tx = self._dex.functions.placeAskToken(
            order_id_b,
            nonce,
            Web3.to_checksum_address(params.base_token),
            Web3.to_checksum_address(params.quote_token),
            price_raw,
            amount_raw,
            expires_at,
        ).build_transaction(self._base_tx())

        receipt = self._send(tx)
        return PlaceOrderResult(
            order_id = "0x" + order_id_b.hex(),
            tx_hash  = receipt["transactionHash"].hex(),
        )

    def place_ask_native(self, params: PlaceAskNativeParams) -> PlaceOrderResult:
        """
        Place a sell order for native BNB.
        BNB is sent as msg.value — no approval needed.
        """
        # For native BNB, baseToken is NATIVE_ADDRESS and baseDecimals = 18
        market = self.get_market_on_chain(NATIVE_ADDRESS, params.quote_token)
        if not market["active"]:
            raise ValueError("BNB market is not active")

        price_raw  = self._to_raw(params.price,  market["quote_decimals"])
        amount_raw = self._to_raw(params.amount, 18)  # BNB is always 18 decimals

        nonce      = self.generate_nonce()
        order_id_b = self.generate_order_id(nonce)
        expires_at = params.expires_at or self._resolve_expiry()

        base_tx = self._base_tx()
        base_tx["value"] = amount_raw

        tx = self._dex.functions.placeAskNative(
            order_id_b,
            nonce,
            Web3.to_checksum_address(params.quote_token),
            price_raw,
            expires_at,
        ).build_transaction(base_tx)

        receipt = self._send(tx)
        return PlaceOrderResult(
            order_id = "0x" + order_id_b.hex(),
            tx_hash  = receipt["transactionHash"].hex(),
        )

    # ─── Place BID (Buy) ──────────────────────────────────────────────────────

    def place_bid(self, params: PlaceBidParams) -> PlaceOrderResult:
        """
        Place a buy order for a token.
        Auto-approves the quote token if ERC20, or sends BNB as msg.value if native.
        """
        market = self.get_market_on_chain(params.base_token, params.quote_token)
        if not market["active"]:
            raise ValueError("Market is not active")

        price_raw  = self._to_raw(params.price,  market["quote_decimals"])
        amount_raw = self._to_raw(params.amount, market["base_decimals"])

        # Calculate required quote escrow: price_raw * amount_raw / 10^baseDecimals
        quote_escrow = (price_raw * amount_raw) // (10 ** market["base_decimals"])

        nonce      = self.generate_nonce()
        order_id_b = self.generate_order_id(nonce)
        expires_at = params.expires_at or self._resolve_expiry()

        is_native_quote = params.quote_token.lower() == NATIVE_ADDRESS

        base_tx = self._base_tx()

        if is_native_quote:
            # Quote is BNB — send as msg.value
            base_tx["value"] = quote_escrow
        else:
            # Quote is ERC20 — auto-approve
            self._ensure_allowance(params.quote_token, quote_escrow)

        tx = self._dex.functions.placeBid(
            order_id_b,
            nonce,
            Web3.to_checksum_address(params.base_token),
            Web3.to_checksum_address(params.quote_token),
            price_raw,
            amount_raw,
            expires_at,
        ).build_transaction(base_tx)

        receipt = self._send(tx)
        return PlaceOrderResult(
            order_id = "0x" + order_id_b.hex(),
            tx_hash  = receipt["transactionHash"].hex(),
        )

    # ─── Cancel ───────────────────────────────────────────────────────────────

    def cancel_order(self, order_id: str) -> str:
        """Cancel your own order. Returns the transaction hash."""
        order_bytes = bytes.fromhex(order_id.removeprefix("0x"))
        tx      = self._dex.functions.cancelOrder(order_bytes).build_transaction(self._base_tx())
        receipt = self._send(tx)
        return receipt["transactionHash"].hex()

    # ─── On-chain Event Listeners ─────────────────────────────────────────────

    def on_order_placed(
        self,
        callback: Callable[[str, str], None],
        poll_interval: float = 2.0,
    ) -> Callable[[], None]:
        """
        Listen for OrderPlaced on-chain events for this wallet.
        Returns a stop function — call it to unsubscribe.
        Uses a background thread with polling (no persistent WebSocket needed).
        """
        import threading

        stop_event = threading.Event()

        def _poll() -> None:
            event_filter = self._dex.events.OrderPlaced.create_filter(  # type: ignore[attr-defined]
                from_block="latest",
                argument_filters={"trader": self._account.address},
            )
            while not stop_event.is_set():
                for entry in event_filter.get_new_entries():
                    order_id = "0x" + entry["args"]["orderId"].hex()
                    tx_hash  = entry["transactionHash"].hex()
                    callback(order_id, tx_hash)
                stop_event.wait(poll_interval)

        thread = threading.Thread(target=_poll, daemon=True)
        thread.start()
        return stop_event.set

    def on_order_matched(
        self,
        callback: Callable[[str, str, str], None],
        poll_interval: float = 2.0,
    ) -> Callable[[], None]:
        """
        Listen for OrderMatched on-chain events involving this wallet.
        Returns a stop function.
        """
        import threading

        stop_event  = threading.Event()
        my_address  = self._account.address.lower()

        def _poll() -> None:
            event_filter = self._dex.events.OrderMatched.create_filter(from_block="latest")  # type: ignore[attr-defined]
            while not stop_event.is_set():
                for entry in event_filter.get_new_entries():
                    args = entry["args"]
                    if (
                        args["askTrader"].lower() == my_address
                        or args["bidTrader"].lower() == my_address
                    ):
                        ask_id  = "0x" + args["askOrderId"].hex()
                        bid_id  = "0x" + args["bidOrderId"].hex()
                        tx_hash = entry["transactionHash"].hex()
                        callback(ask_id, bid_id, tx_hash)
                stop_event.wait(poll_interval)

        thread = threading.Thread(target=_poll, daemon=True)
        thread.start()
        return stop_event.set

    def on_order_cancelled(
        self,
        callback: Callable[[str, str], None],
        poll_interval: float = 2.0,
    ) -> Callable[[], None]:
        """
        Listen for OrderCancelled on-chain events for this wallet.
        Returns a stop function.
        """
        import threading

        stop_event = threading.Event()

        def _poll() -> None:
            event_filter = self._dex.events.OrderCancelled.create_filter(  # type: ignore[attr-defined]
                from_block="latest",
                argument_filters={"trader": self._account.address},
            )
            while not stop_event.is_set():
                for entry in event_filter.get_new_entries():
                    order_id = "0x" + entry["args"]["orderId"].hex()
                    tx_hash  = entry["transactionHash"].hex()
                    callback(order_id, tx_hash)
                stop_event.wait(poll_interval)

        thread = threading.Thread(target=_poll, daemon=True)
        thread.start()
        return stop_event.set

    # ─── Internal Helpers ─────────────────────────────────────────────────────

    def _to_raw(self, value: float | str, decimals: int) -> int:
        """Convert a human-readable number to raw integer units."""
        return int(float(value) * 10 ** decimals)

    def _resolve_expiry(self) -> int:
        """Compute the default expiry timestamp."""
        return int(time.time()) + self.get_default_expiry()

    def _base_tx(self) -> dict:
        """Build base transaction parameters."""
        return {
            "from":     self._account.address,
            "chainId":  self._chain.chain_id,
            "nonce":    self._w3.eth.get_transaction_count(self._account.address),
            "gasPrice": self._w3.eth.gas_price,
        }

    def _send(self, tx: dict) -> TxReceipt:
        """Estimate gas, sign, broadcast, and wait for receipt."""
        tx["gas"] = self._w3.eth.estimate_gas(tx)
        signed    = self._account.sign_transaction(tx)
        tx_hash   = self._w3.eth.send_raw_transaction(signed.raw_transaction)
        return self._w3.eth.wait_for_transaction_receipt(tx_hash)
