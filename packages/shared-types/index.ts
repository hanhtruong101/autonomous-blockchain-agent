// Proposal amounts are bounded safe integers. Unbounded chain balances use strings.
// Financial arithmetic in the UI uses BigInt; policy decimal values are strings.
export interface GenerationMetadata {
  provider: "offline" | "openai" | "ollama" | "fixture";
  model: string | null;
  schema_version: string;
  execution_mode:
    | "deterministic"
    | "deterministic_with_ai_explanation"
    | "ai_decision_deterministic_sizing"
    | "ai_trade_proposal"
    | "fixture"
    | null;
}
export interface Configuration {
  generation: GenerationMetadata;
  interpreter: "local" | "llm";
  provider_host: string;
}
export interface PolicyDraft {
  maximum_trade_amount: string;
  minimum_usdc_ratio: string | null;
  daily_spending_limit: { asset: "USDC"; amount: string };
  allowed_assets: string[];
  allowed_protocols: string[];
  allowed_contracts: string[];
  rebalance: {
    enabled: boolean;
    minimum_interval_hours: number;
    tolerance_bps: number;
  };
  portfolio_targets: { USDC: string; WETH: string };
  maximum_slippage_bps: number;
}
export interface Policy {
  target_usdc_percent: string;
  target_weth_percent: string;
  accepted_usdc_range: string;
  minimum_usdc_percent: string | null;
  id: string;
  policy_id: string;
  goal: string;
  status: string;
  draft: PolicyDraft;
  created_at: string;
}
export interface Wallet {
  address: string;
  chain_id: number;
  usdc_units: string;
  weth_units: string;
  spent_units: string;
  block_timestamp: number;
}
export interface Rule {
  rule_name: string;
  passed: boolean;
  reason: string;
  observed_value: string;
  required_value: string;
}
export interface Finding {
  check: string;
  level: "LOW" | "MEDIUM" | "HIGH";
  explanation: string;
}
export interface Approval {
  id: string;
  proposal_id: string;
  status: string;
  expires_at: string;
  decided_by: string | null;
}
export interface Execution {
  id: string;
  proposal_id: string;
  transaction_hash: string | null;
  status: string;
  created_at: string;
}
export interface Proposal {
  generation: GenerationMetadata | null;
  id: string;
  status: string;
  proposal: {
    id: string;
    policy_version_id: string;
    action_type: string;
    chain_id: number;
    wallet: string;
    asset_in: string;
    asset_out: string;
    amount: number;
    destination: string;
    protocol: string;
    contract_address: string;
    operation: string;
    maximum_slippage_bps: number;
    reason: string;
    created_at: string;
  };
  evaluation: {
    policy: { allowed: boolean; rules: Rule[] };
    simulation: {
      success: boolean;
      estimated_gas: number;
      expected_token_changes: { asset: string; units: number }[];
      contract_called: string;
      revert_reason: string | null;
      expected_output: number;
      slippage_bps: number;
    };
    risk: { level: string; findings: Finding[] };
    outcome: string;
  } | null;
  approval: Approval | null;
  execution: Execution | null;
}
export interface AuditEvent {
  id: number;
  event: string;
  entity_id: string;
  actor: string;
  details: string;
  created_at: string;
}

export interface Readiness {
  code:
    | "READY"
    | "WAITING_INTERVAL"
    | "BUDGET_EXHAUSTED"
    | "NO_TRADE"
    | "FROZEN"
    | "PENDING_REVIEW"
    | "RECONCILIATION"
    | "GENERATING"
    | "NO_POLICY"
    | "UNAVAILABLE";
  reason: string;
  next_step: string;
  eligible_after: string | null;
  proposal_id: string | null;
  generation_started_at: string | null;
}
export interface AutomationState {
  readiness: Readiness;
  enabled: boolean;
  running: boolean;
  execution_paused: boolean;
  generation_in_progress: boolean;
  policy_version_id: string | null;
  interval_seconds: number;
  next_check_at: string | null;
  last_check_at: string | null;
  last_result: string;
  consecutive_failures: number;
  worker_available: boolean;
}
export interface EvaluationRow {
  agent_action: string | null;
  decision_matches_expected: boolean | null;
  sizing_matches_expected: boolean | null;
  scenario: string;
  expected_action: string;
  expected_amount_units: number;
  actual_action: string;
  actual_amount_units: number;
  matches_expected: boolean;
  decision: string;
  latency_ms: number;
  safety_violations: string[];
  error: string | null;
}
export interface EvaluationReport {
  benchmark_kind:
    | "legacy_raw_proposals"
    | "bounded_decisions"
    | "deterministic"
    | "ai_trade_proposals";
  decision_matches: number;
  decision_cases: number;
  sizing_matches: number;
  sizing_cases: number;
  provider: string;
  model: string | null;
  created_at: string;
  execution: string;
  rows: EvaluationRow[];
  correct: number;
  total: number;
  proposed_trades: number;
  approval_requests: number;
  blocked: number;
  invalid_outputs: number;
  total_latency_ms: number;
  limitation: string;
}
export interface EvaluationView {
  deterministic: EvaluationReport;
  ollama_shadow: EvaluationReport | null;
  shadow_status: string;
}

export interface AgentActivityItem {
  id: string;
  updated_at: string;
  policy_version_id: string | null;
  source: "manual" | "scheduled" | "fixture";
  state:
    | "OBSERVING"
    | "DECIDING"
    | "SYSTEM_SKIPPED"
    | "AI_HOLD"
    | "HOLD"
    | "PROPOSAL_CREATED"
    | "FAILED"
    | "CANCELLED";
  reason: string;
  generation: GenerationMetadata | null;
  observation: {
    usdc_units: string;
    weth_units: string;
    spent_units: string;
    block_timestamp: number;
  } | null;
  decision: { action: "HOLD" | "REBALANCE" | "SWAP"; reason: string } | null;
  calculation: string | null;
  proposal_id: string | null;
  proposal_status: string | null;
}
export interface AgentActivityView {
  items: AgentActivityItem[];
  consecutive_ai_holds: number;
}
