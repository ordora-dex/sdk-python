from .types import ChainConfig

# ─── Addresses ────────────────────────────────────────────────────────────────

NATIVE_ADDRESS = "0x0000000000000000000000000000000000000000"

MAX_UINT256 = 2**256 - 1

# ─── Chain Configurations ─────────────────────────────────────────────────────

CHAIN_CONFIGS: dict[str, ChainConfig] = {
    "bsc-testnet": ChainConfig(
        chain_id         = 97,
        rpc_url          = "https://data-seed-prebsc-1-s1.binance.org:8545",
        contract_address = "0x9466a9259075859E14897AE556ca0B449BdF6e6D",
        wbnb_address     = "0xae13d989daC2f0dEbFf460aC112a837C89BAa7cd",
        explorer_url     = "https://testnet.bscscan.com",
    ),
    "bsc-mainnet": ChainConfig(
        chain_id         = 56,
        rpc_url          = "https://bsc-dataseed1.binance.org",
        contract_address = "",  # fill in when mainnet is deployed
        wbnb_address     = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        explorer_url     = "https://bscscan.com",
    ),
}

# ─── Default Hasura Endpoints ─────────────────────────────────────────────────

HASURA_HTTP_URL = "https://hasura.ordora.xyz/v1/graphql"
HASURA_WS_URL   = "wss://hasura.ordora.xyz/v1/graphql"

# ─── Minimal ERC20 ABI ───────────────────────────────────────────────────────

ERC20_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "owner",   "type": "address"},
            {"internalType": "address", "name": "spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "spender", "type": "address"},
            {"internalType": "uint256", "name": "amount",  "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
]
