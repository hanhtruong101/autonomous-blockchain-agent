"""A-D and medium-approval demo against the running local API. Start from a fresh stack."""

import os

import httpx


def main() -> None:
    client = httpx.Client(
        base_url="http://localhost:8000",
        timeout=60,
        headers={"Authorization": "Bearer " + os.environ["AUTONOMY_OWNER_TOKEN"]},
    )
    goal = (
        "Keep approximately 70% of my portfolio in USDC, "
        "never spend more than 100 USDC per day, rebalance on demand, "
        "and only interact with approved protocols."
    )
    response = client.post("/policies", json={"goal": goal})
    response.raise_for_status()
    draft = response.json()
    print("Review the interpreted policy before activation:")
    print(draft["draft"])
    if input("Type APPROVE to activate this exact policy: ") != "APPROVE":
        return
    client.post(f"/policies/{draft['id']}/approve").raise_for_status()
    for scenario, expected in [
        ("A", "EXECUTED"),
        ("B", "BLOCKED"),
        ("C", "BLOCKED"),
        ("D", "BLOCKED"),
    ]:
        response = client.post("/agent/runs", json={"scenario": scenario})
        response.raise_for_status()
        proposal = response.json()
        assert proposal["status"] == expected, proposal
        print(scenario, proposal["status"], proposal["id"])
    response = client.post("/agent/runs", json={"scenario": "medium"})
    response.raise_for_status()
    proposal = response.json()
    assert proposal["status"] == "AWAITING_APPROVAL", proposal
    print("Review the 70-unit medium-risk proposal in the browser:", proposal["id"])
    print("This completes the 100-unit daily allowance if you approve it.")


if __name__ == "__main__":
    main()
