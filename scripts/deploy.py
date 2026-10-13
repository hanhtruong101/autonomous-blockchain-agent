"""Deploy to a fresh local Anvil. Uses public unlocked DEVELOPMENT accounts only."""

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from web3 import Web3
from web3.types import Wei


def main() -> None:
    rpc_url = os.environ.get("AUTONOMY_RPC_URL", "http://127.0.0.1:8545")
    rpc = urlparse(rpc_url)
    if (
        rpc.scheme != "http"
        or rpc.hostname not in {"localhost", "127.0.0.1", "anvil"}
        or rpc.username
        or rpc.password
        or rpc.query
        or rpc.fragment
    ):
        raise RuntimeError("Deployment requires a local Anvil RPC URL")
    web3 = Web3(Web3.HTTPProvider(rpc_url))
    if web3.eth.chain_id != 31337 or "anvil" not in web3.client_version.lower():
        raise RuntimeError("Deployment requires local Anvil 31337")
    accounts = list(web3.eth.accounts)
    owner, agent, recipient = accounts[0], accounts[1], accounts[2]
    if web3.eth.get_transaction_count(owner) != 0:
        raise RuntimeError("Use a fresh Anvil instance for deterministic deployment")

    def deploy(name: str, *args: Any) -> Any:
        artifact = json.loads(Path(f"contracts/out/{name}.sol/{name}.json").read_text())
        factory = web3.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"]["object"])
        receipt = web3.eth.wait_for_transaction_receipt(
            factory.constructor(*args).transact({"from": owner})
        )
        if receipt["status"] != 1 or not receipt["contractAddress"]:
            raise RuntimeError("Deployment failed")
        return web3.eth.contract(address=receipt["contractAddress"], abi=artifact["abi"])

    def send(function: Any) -> None:
        receipt = web3.eth.wait_for_transaction_receipt(function.transact({"from": owner}))
        if receipt["status"] != 1:
            raise RuntimeError("Seeding failed")

    usdc = deploy("MockUSDC", "TestUSDC")
    weth = deploy("MockUSDC", "TestWETH")
    dex = deploy("MockDex", usdc.address, weth.address)
    account = deploy("PolicySmartAccount", owner, agent, usdc.address, weth.address, 100_000_000)
    send(account.functions.setTarget(dex.address, True))
    send(account.functions.setTarget(recipient, True))
    send(usdc.functions.mint(account.address, 1_000_000_000))
    send(usdc.functions.mint(dex.address, 10_000_000_000))
    send(weth.functions.mint(dex.address, 10_000_000_000))
    web3.eth.wait_for_transaction_receipt(
        web3.eth.send_transaction({"from": owner, "to": account.address, "value": Wei(10**18)})
    )
    data = dict(
        chain_id=31337,
        owner=owner,
        agent=agent,
        recipient=recipient,
        usdc=usdc.address,
        weth=weth.address,
        dex=dex.address,
        account=account.address,
    )
    path = Path(os.environ.get("AUTONOMY_DEPLOYMENT_PATH", "local/deployment.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    print("Deployed fake assets on local Anvil. Public development accounts: NEVER use real funds.")


if __name__ == "__main__":
    main()
