from datetime import timedelta

from app.models.entities import ApprovalRequest, Proposal
from app.schemas.domain import TransactionProposal, now
from conftest import GOAL, FakeAdapter
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker


def activate(client: TestClient, maximum_trade_amount: str = "100") -> str:
    draft = client.post(
        "/policies", json={"goal": GOAL, "maximum_trade_amount": maximum_trade_amount}
    )
    assert draft.status_code == 201, draft.text
    identifier = str(draft.json()["id"])
    assert client.post(f"/policies/{identifier}/approve").status_code == 200
    return identifier


def test_policy_requires_approval(client: TestClient, adapter: FakeAdapter) -> None:
    client.post("/policies", json={"goal": GOAL})
    assert client.post("/agent/runs", json={}).status_code == 409
    assert adapter.calls == 0


def test_auth(client: TestClient) -> None:
    assert client.get("/wallet/state", headers={"Authorization": "invalid"}).status_code == 401


def test_scenarios(client: TestClient, adapter: FakeAdapter) -> None:
    activate(client)
    for scenario, expected in [
        ("A", "EXECUTED"),
        ("B", "BLOCKED"),
        ("C", "BLOCKED"),
        ("D", "BLOCKED"),
    ]:
        response = client.post("/agent/runs", json={"scenario": scenario})
        assert response.status_code == 201, response.text
        assert response.json()["status"] == expected
    assert adapter.calls == 1
    events = {item["event"] for item in client.get("/audit-events").json()}
    assert {
        "TRANSACTION_CONFIRMED",
        "TRANSACTION_BLOCKED",
        "RISK_ASSESSED",
        "SIMULATION_COMPLETED",
    } <= events


def test_medium_exact_approval(client: TestClient, adapter: FakeAdapter) -> None:
    activate(client)
    response = client.post("/agent/runs", json={"scenario": "medium"}).json()
    assert response["status"] == "AWAITING_APPROVAL"
    assert adapter.calls == 0
    identifier = response["approval"]["id"]
    approved = client.post(f"/approvals/{identifier}/approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "EXECUTED"
    assert client.post(f"/approvals/{identifier}/approve").status_code == 409
    assert adapter.calls == 1


def test_reject(client: TestClient, adapter: FakeAdapter) -> None:
    activate(client)
    response = client.post("/agent/runs", json={"scenario": "medium"}).json()
    assert (
        client.post(f"/approvals/{response['approval']['id']}/reject").json()["status"]
        == "REJECTED"
    )
    assert adapter.calls == 0


def test_expired_approval(
    client: TestClient, sessions: sessionmaker[Session], adapter: FakeAdapter
) -> None:
    activate(client)
    response = client.post("/agent/runs", json={"scenario": "medium"}).json()
    with sessions.begin() as session:
        approval = session.get(ApprovalRequest, response["approval"]["id"])
        assert approval is not None
        approval.expires_at = now() - timedelta(seconds=1)
    assert client.post(f"/approvals/{response['approval']['id']}/approve").status_code == 409
    assert adapter.calls == 0


def test_modified_proposal(
    client: TestClient, sessions: sessionmaker[Session], adapter: FakeAdapter
) -> None:
    activate(client)
    response = client.post("/agent/runs", json={"scenario": "medium"}).json()
    with sessions.begin() as session:
        row = session.get(Proposal, response["id"])
        assert row is not None
        row.proposal_json = (
            TransactionProposal.model_validate_json(row.proposal_json)
            .model_copy(update={"amount": 1})
            .model_dump_json()
        )
    assert client.post(f"/approvals/{response['approval']['id']}/approve").status_code == 409
    assert adapter.calls == 0


def test_changed_policy(client: TestClient, adapter: FakeAdapter) -> None:
    first = activate(client)
    response = client.post("/agent/runs", json={"scenario": "medium"}).json()
    second = activate(client)
    assert first != second
    assert client.get(f"/policies/{first}").json()["status"] == "SUPERSEDED"
    assert client.post(f"/approvals/{response['approval']['id']}/approve").status_code == 409
    assert adapter.calls == 0


def test_simulation_revert(client: TestClient, adapter: FakeAdapter) -> None:
    activate(client)
    adapter.fail_simulation = True
    assert client.post("/agent/runs", json={"scenario": "A"}).json()["status"] == "BLOCKED"
    assert adapter.calls == 0


def test_uncertain_freezes_wallet(client: TestClient, adapter: FakeAdapter) -> None:
    activate(client)
    adapter.fail_submit = True
    assert client.post("/agent/runs", json={"scenario": "A"}).json()["status"] == "UNCERTAIN"
    assert client.post("/agent/runs", json={"scenario": "A"}).status_code == 409
    assert client.post("/policies", json={"goal": GOAL}).status_code == 409
    assert adapter.calls == 1


def test_failed_receipt(
    client: TestClient, adapter: FakeAdapter, sessions: sessionmaker[Session]
) -> None:
    activate(client)
    adapter.receipt_success = False
    assert client.post("/agent/runs", json={"scenario": "A"}).json()["status"] == "FAILED"
    with sessions() as session:
        assert session.scalar(select(Proposal)) is not None
