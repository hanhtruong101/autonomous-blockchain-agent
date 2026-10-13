"""Read-only startup checks; never print secrets or change the local stack."""

import json
import os
import socket
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def probe(label: str, url: str, payload: bytes | None = None) -> None:
    if urlsplit(url).hostname not in {"localhost", "127.0.0.1", "anvil"}:
        print(f"{label}: skipped; only local endpoints are supported")
        return
    try:
        request = Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=3) as response:
            result = json.loads(response.read(100_000))
        if label == "Anvil" and result.get("result") != "0x7a69":
            print("Anvil: wrong chain; execution must remain disabled")
        else:
            print(f"{label}: reachable")
    except Exception:
        print(f"{label}: unavailable; check the service and its configured local port")


def main() -> None:
    probe("API", "http://127.0.0.1:8000/openapi.json")
    probe(
        "Anvil",
        os.environ.get("AUTONOMY_RPC_URL", "http://127.0.0.1:8545"),
        b'{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}',
    )
    if os.environ.get("AUTONOMY_AI_PROVIDER") == "ollama":
        probe("Ollama", "http://127.0.0.1:11434/api/tags")
    db = urlsplit(os.environ.get("AUTONOMY_DATABASE_URL", "postgresql://localhost:5432/autonomy"))
    if db.hostname in {"localhost", "127.0.0.1", "postgres"}:
        try:
            with socket.create_connection((db.hostname, db.port or 5432), timeout=3):
                print("PostgreSQL: TCP reachable; credentials and migrations are not verified")
        except OSError:
            print("PostgreSQL: unavailable on the configured local port")
    print("Next: sign in, review an approved policy, then inspect Agent activity readiness.")


if __name__ == "__main__":
    main()
