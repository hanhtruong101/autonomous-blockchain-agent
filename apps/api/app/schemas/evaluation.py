"""Typed, read-only benchmark artifacts. No signing or execution capability."""

from typing import Literal

from app.schemas.domain import Model


class EvaluationRow(Model):
    agent_action: str | None = None
    decision_matches_expected: bool | None = None
    sizing_matches_expected: bool | None = None
    scenario: str
    expected_action: str
    expected_amount_units: int
    actual_action: str
    actual_amount_units: int
    matches_expected: bool
    decision: str
    latency_ms: int
    safety_violations: tuple[str, ...] = ()
    error: str | None = None


class EvaluationReport(Model):
    benchmark_kind: Literal[
        "legacy_raw_proposals", "bounded_decisions", "deterministic", "ai_trade_proposals"
    ] = "legacy_raw_proposals"
    decision_matches: int = 0
    decision_cases: int = 0
    sizing_matches: int = 0
    sizing_cases: int = 0
    provider: str
    model: str | None = None
    created_at: str
    execution: str = "NONE: synthetic snapshots only; no RPC, signing or transactions"
    rows: tuple[EvaluationRow, ...]
    correct: int
    total: int
    proposed_trades: int
    approval_requests: int
    blocked: int
    invalid_outputs: int
    total_latency_ms: int
    limitation: str = (
        "Single-step synthetic correctness and intervention proxies; "
        "not measured human time savings."
    )


class EvaluationView(Model):
    deterministic: EvaluationReport
    ollama_shadow: EvaluationReport | None = None
    shadow_status: str
