"""Polygon blockchain audit trail (Phase 5.3).

Anchors (file_hash, verdict, timestamp) on the TrustSphereAudit contract on
Polygon **Amoy** testnet (Mumbai was decommissioned in 2024). Fully gated
behind env config — if the wallet/contract isn't configured or the RPC is
unreachable, anchoring is *skipped* with a reason instead of failing the
analysis pipeline.

Required .env:
    POLYGON_RPC_URL                (default: https://rpc-amoy.polygon.technology)
    POLYGON_PRIVATE_KEY            funded Amoy test wallet (faucet.polygon.technology)
    TRUSTSPHERE_CONTRACT_ADDRESS   from scripts/deploy_contract.py
    POLYGON_CHAIN_ID               default 80002 (Amoy)
"""
import os
import time

DEFAULT_RPC = "https://rpc-amoy.polygon.technology"
DEFAULT_CHAIN_ID = 80002  # Polygon Amoy
NETWORK_NAME = "polygon-amoy"

CONTRACT_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "fileHash", "type": "string"},
            {"internalType": "string", "name": "verdict", "type": "string"},
            {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
        ],
        "name": "storeVerdict",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "string", "name": "fileHash", "type": "string"}],
        "name": "getVerdict",
        "outputs": [
            {"internalType": "string", "name": "verdict", "type": "string"},
            {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
            {"internalType": "uint256", "name": "blockTime", "type": "uint256"},
            {"internalType": "address", "name": "submitter", "type": "address"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "bytes32", "name": "fileHashId", "type": "bytes32"},
            {"indexed": False, "internalType": "string", "name": "fileHash", "type": "string"},
            {"indexed": False, "internalType": "string", "name": "verdict", "type": "string"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"},
            {"indexed": False, "internalType": "address", "name": "submitter", "type": "address"},
        ],
        "name": "VerdictStored",
        "type": "event",
    },
]


def _config():
    return {
        "rpc_url": os.getenv("POLYGON_RPC_URL", DEFAULT_RPC),
        "private_key": os.getenv("POLYGON_PRIVATE_KEY", "").strip(),
        "contract_address": os.getenv("TRUSTSPHERE_CONTRACT_ADDRESS", "").strip(),
        "chain_id": int(os.getenv("POLYGON_CHAIN_ID", DEFAULT_CHAIN_ID)),
    }


def is_configured() -> bool:
    cfg = _config()
    return bool(cfg["private_key"] and cfg["contract_address"])


def _connect(cfg):
    from web3 import Web3
    from web3.middleware import ExtraDataToPOAMiddleware

    w3 = Web3(Web3.HTTPProvider(cfg["rpc_url"], request_kwargs={"timeout": 30}))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)  # Polygon is PoA
    if not w3.is_connected():
        raise ConnectionError(f"RPC unreachable: {cfg['rpc_url']}")
    return w3


def with_0x(tx_hash: str | None) -> str | None:
    """Transaction hashes must start with 0x for the explorer. Recent web3/hexbytes versions return them without it."""
    if not tx_hash:
        return tx_hash
    return "0x" + tx_hash.removeprefix("0x")


def explorer_tx_url(tx_hash: str | None) -> str | None:
    return f"https://amoy.polygonscan.com/tx/{with_0x(tx_hash)}" if tx_hash else None


def anchor_verdict(file_hash: str, verdict: str, timestamp: int | None = None) -> dict:
    """Write the verdict on-chain. Never raises — returns a status dict:

    {status: "anchored"|"pending"|"skipped"|"error", tx_hash, network, reason,
     block_number, explorer_url}
    """
    result = {
        "status": "skipped",
        "tx_hash": None,
        "network": NETWORK_NAME,
        "reason": None,
        "block_number": None,
        "explorer_url": None,
    }
    cfg = _config()
    if os.getenv("TRUSTSPHERE_ANCHOR", "on").strip().lower() in ("off", "0", "false", "no"):
        result["reason"] = "anchoring switched off (TRUSTSPHERE_ANCHOR=off)"
        return result
    if not cfg["private_key"]:
        result["reason"] = "POLYGON_PRIVATE_KEY not set — anchoring disabled"
        return result
    if not cfg["contract_address"]:
        result["reason"] = "TRUSTSPHERE_CONTRACT_ADDRESS not set — deploy contract first"
        return result

    try:
        from web3 import Web3

        w3 = _connect(cfg)
        account = w3.eth.account.from_key(cfg["private_key"])
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(cfg["contract_address"]), abi=CONTRACT_ABI
        )

        ts = int(timestamp if timestamp is not None else time.time())
        tx = contract.functions.storeVerdict(file_hash, verdict, ts).build_transaction(
            {
                "from": account.address,
                "nonce": w3.eth.get_transaction_count(account.address),
                "chainId": cfg["chain_id"],
                "gasPrice": w3.eth.gas_price,
            }
        )
        tx["gas"] = int(w3.eth.estimate_gas(tx) * 1.2)

        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        result["tx_hash"] = with_0x(tx_hash.hex())
        result["explorer_url"] = explorer_tx_url(tx_hash.hex())

        try:
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=90)
            result["block_number"] = receipt.blockNumber
            result["status"] = "anchored" if receipt.status == 1 else "error"
            if receipt.status != 1:
                result["reason"] = "transaction reverted"
        except Exception:
            # Sent but not yet mined — still recoverable via the tx hash.
            result["status"] = "pending"
            result["reason"] = "tx sent; receipt not confirmed within 90s"
        return result

    except Exception as exc:
        result["status"] = "error"
        result["reason"] = f"{type(exc).__name__}: {exc}"
        return result


def read_verdict(file_hash: str) -> dict | None:
    """Read back an anchored verdict from the chain (for /api/verify)."""
    cfg = _config()
    if not cfg["contract_address"]:
        return None
    try:
        from web3 import Web3

        w3 = _connect(cfg)
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(cfg["contract_address"]), abi=CONTRACT_ABI
        )
        verdict, ts, block_time, submitter = contract.functions.getVerdict(file_hash).call()
        if not verdict:
            return None
        return {
            "verdict": verdict,
            "timestamp": ts,
            "block_time": block_time,
            "submitter": submitter,
            "network": NETWORK_NAME,
        }
    except Exception:
        return None
