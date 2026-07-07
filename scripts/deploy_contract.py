"""Deploy TrustSphereAudit.sol to Polygon Amoy testnet (Phase 5.3, one-time).

Prerequisites (see PROJECT_STATE.md §5):
  1. Create a throwaway wallet (e.g. MetaMask) and export its private key.
  2. Fund it with test POL: https://faucet.polygon.technology (network: Amoy).
  3. Put POLYGON_PRIVATE_KEY=<key> in backend/.env.

Run from repo root:
  .\\backend\\venv\\Scripts\\python.exe scripts\\deploy_contract.py

On success it prints the contract address — paste it into backend/.env as
TRUSTSPHERE_CONTRACT_ADDRESS=<address>.
"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

load_dotenv(BACKEND / ".env")

SOLC_VERSION = "0.8.19"
CONTRACT_PATH = BACKEND / "contracts" / "TrustSphereAudit.sol"


def main():
    private_key = os.getenv("POLYGON_PRIVATE_KEY", "").strip()
    rpc_url = os.getenv("POLYGON_RPC_URL", "https://rpc-amoy.polygon.technology")
    chain_id = int(os.getenv("POLYGON_CHAIN_ID", 80002))

    if not private_key:
        sys.exit("POLYGON_PRIVATE_KEY is not set in backend/.env — create a test wallet, "
                 "fund it at https://faucet.polygon.technology (Amoy), then retry.")

    import solcx
    from web3 import Web3
    from web3.middleware import ExtraDataToPOAMiddleware

    print(f"[1/4] Ensuring solc {SOLC_VERSION} is installed...")
    if SOLC_VERSION not in [str(v) for v in solcx.get_installed_solc_versions()]:
        solcx.install_solc(SOLC_VERSION)

    print("[2/4] Compiling TrustSphereAudit.sol...")
    compiled = solcx.compile_source(
        CONTRACT_PATH.read_text(),
        output_values=["abi", "bin"],
        solc_version=SOLC_VERSION,
    )
    _, contract_iface = compiled.popitem()

    print(f"[3/4] Connecting to {rpc_url} (chain {chain_id})...")
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 30}))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    if not w3.is_connected():
        sys.exit(f"RPC unreachable: {rpc_url}")

    account = w3.eth.account.from_key(private_key)
    balance = w3.eth.get_balance(account.address)
    print(f"      Deployer: {account.address}  balance: {w3.from_wei(balance, 'ether')} POL")
    if balance == 0:
        sys.exit("Wallet has 0 POL — get test funds from https://faucet.polygon.technology "
                 "(select Polygon Amoy) and retry.")

    print("[4/4] Deploying...")
    contract = w3.eth.contract(abi=contract_iface["abi"], bytecode=contract_iface["bin"])
    tx = contract.constructor().build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "chainId": chain_id,
            "gasPrice": w3.eth.gas_price,
        }
    )
    tx["gas"] = int(w3.eth.estimate_gas(tx) * 1.2)
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"      tx: 0x{tx_hash.hex().removeprefix('0x')} — waiting for confirmation...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

    if receipt.status != 1:
        sys.exit("Deployment transaction reverted.")

    print("\n[OK] Deployed TrustSphereAudit")
    print(f"   Contract address: {receipt.contractAddress}")
    print(f"   Explorer: https://amoy.polygonscan.com/address/{receipt.contractAddress}")
    print("\nAdd this line to backend/.env:")
    print(f"   TRUSTSPHERE_CONTRACT_ADDRESS={receipt.contractAddress}")


if __name__ == "__main__":
    main()
