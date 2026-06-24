"""
Ordora DEX Python SDK
~~~~~~~~~~~~~~~~~~~~~

Official Python SDK for the Ordora DEX — place orders, monitor status,
and stream real-time market data.

Basic usage::

    import os
    import asyncio
    from ordora_sdk import OrdoraSDK, PlaceAskNativeParams

    sdk = OrdoraSDK(private_key=os.environ["PRIVATE_KEY"])

    # Place a sell order (synchronous)
    result = sdk.place_ask_native(PlaceAskNativeParams(
        quote_token="0x337610d27c682E347C9cD60BD4b3b107C9d34dDd",
        price=310.0,
        amount=0.01,
    ))
    print("Order ID:", result.order_id)

    # Query Hasura (async)
    markets = asyncio.run(sdk.get_markets())
    for m in markets:
        print(m.pair_symbol)
"""

from .sdk import OrdoraSDK
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
from .constants import CHAIN_CONFIGS, HASURA_HTTP_URL, HASURA_WS_URL, NATIVE_ADDRESS

__all__ = [
    "OrdoraSDK",
    # params
    "PlaceAskTokenParams",
    "PlaceAskNativeParams",
    "PlaceBidParams",
    # results
    "PlaceOrderResult",
    "ApprovalResult",
    # data models
    "Market",
    "Order",
    "Trade",
    "Ticker",
    "Token",
    "LockedAsset",
    "OnChainOrder",
    "PaginatedResult",
    # config
    "ChainConfig",
    "CHAIN_CONFIGS",
    "HASURA_HTTP_URL",
    "HASURA_WS_URL",
    "NATIVE_ADDRESS",
]

__version__ = "0.1.0"
