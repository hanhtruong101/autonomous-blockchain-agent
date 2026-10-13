import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import type { Proposal } from "../../../../packages/shared-types";
import { api, units } from "../api";
import { ErrorMessage, Panel, Status } from "../components";

export function TransactionDetail() {
  const { id } = useParams();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["proposal", id],
    queryFn: () => api<Proposal>(`/proposals/${id}`),
  });
  const decision = useMutation({
    mutationFn: (action: "approve" | "reject") =>
      api<Proposal>(`/approvals/${query.data?.approval?.id}/${action}`, {}),
    onSuccess: () => queryClient.invalidateQueries(),
  });
  const reconcile = useMutation({
    mutationFn: () => api<Proposal>(`/proposals/${id}/reconcile`, {}),
    onSuccess: () => queryClient.invalidateQueries(),
  });
  if (!query.data)
    return (
      <>
        <h1>Transaction detail</h1>
        <ErrorMessage error={query.error} />
        <p>Loading…</p>
      </>
    );
  const {
    proposal: p,
    evaluation: e,
    approval,
    execution,
    status,
  } = query.data;
  return (
    <>
      <div className="page-heading">
        <h1>Transaction detail.</h1>
        <Status value={status} />
      </div>
      <p className="lede">
        {units(p.amount)} {p.asset_in} → {p.asset_out} via {p.protocol}
      </p>
      {status === "BLOCKED" && (
        <Panel title="Why this proposal was blocked">
          <ul>
            {e?.policy.rules
              .filter((rule) => !rule.passed)
              .map((rule) => (
                <li key={rule.rule_name}>{rule.reason}</li>
              ))}
          </ul>
          {e?.risk.findings
            .filter((finding) => finding.level === "HIGH")
            .map((finding) => (
              <p key={finding.check}>{finding.explanation}</p>
            ))}
          <p>
            This historical proposal will not be retried. Check current
            readiness, then create a new proposal when permitted.
          </p>
          <Link to="/activity">View readiness and next steps →</Link>
        </Panel>
      )}
      <Panel
        title={
          query.data.generation?.execution_mode === "ai_trade_proposal"
            ? "AI trade proposal and reasoning"
            : "Calculated plan and explanation"
        }
      >
        <p>{p.reason}</p>
        <p>
          Method:{" "}
          {query.data.generation?.execution_mode?.replaceAll("_", " ") ??
            "Historical proposal"}
          . Provider: {query.data.generation?.provider ?? "Not recorded"}{" "}
          {query.data.generation?.model ?? ""}
        </p>
        <dl>
          <dt>Destination</dt>
          <dd className="mono">{p.destination}</dd>
          <dt>Contract</dt>
          <dd className="mono">{p.contract_address}</dd>
          <dt>Operation</dt>
          <dd>{p.operation}</dd>
          <dt>Maximum slippage</dt>
          <dd>{p.maximum_slippage_bps} basis points</dd>
          <dt>Policy version</dt>
          <dd>
            <Link to={`/policies/${p.policy_version_id}`}>
              {p.policy_version_id}
            </Link>
          </dd>
        </dl>
      </Panel>
      <Panel title="Deterministic policy checks">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Rule</th>
                <th>Result</th>
                <th>Observed</th>
                <th>Required</th>
              </tr>
            </thead>
            <tbody>
              {e?.policy.rules.map((rule) => (
                <tr key={rule.rule_name}>
                  <td>{rule.rule_name.replaceAll("_", " ")}</td>
                  <td>
                    <Status value={rule.passed ? "PASS" : "BLOCKED"} />
                  </td>
                  <td className="mono">{rule.observed_value}</td>
                  <td className="mono">{rule.required_value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <div className="columns">
        <Panel title="RPC simulation">
          <Status value={e?.simulation.success ? "PASS" : "BLOCKED"} />
          <p>Estimated gas: {e?.simulation.estimated_gas ?? "—"}</p>
          <p>
            Expected output: {units(e?.simulation.expected_output ?? 0)}{" "}
            {p.asset_out}
          </p>
          <p>
            Simulated slippage: {e?.simulation.slippage_bps ?? 0} basis points
          </p>
          {e?.simulation.revert_reason && <p>{e.simulation.revert_reason}</p>}
          <p className="muted">
            Expected changes use the fixed mock exchange rate. Simulation cannot
            guarantee execution.
          </p>
        </Panel>
        <Panel title="Risk assessment">
          <Status value={e?.risk.level ?? "PENDING"} />
          {e?.risk.findings.length === 0 ? (
            <p>No deterministic risk findings.</p>
          ) : (
            <ul>
              {e?.risk.findings.map((finding) => (
                <li key={finding.check}>{finding.explanation}</li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
      <Panel title="Approval and execution">
        <p>Decision: {e?.outcome ?? "Pending"}</p>
        {approval && (
          <p>
            Owner decision: <Status value={approval.status} /> · Expires{" "}
            {new Date(approval.expires_at).toLocaleString()}
          </p>
        )}
        {status === "AWAITING_APPROVAL" && (
          <div className="actions">
            <button
              disabled={decision.isPending}
              onClick={() => decision.mutate("approve")}
            >
              Approve this exact transaction
            </button>
            <button
              className="secondary"
              disabled={decision.isPending}
              onClick={() => decision.mutate("reject")}
            >
              Reject
            </button>
          </div>
        )}
        <ErrorMessage error={decision.error ?? reconcile.error} />
        {execution?.transaction_hash ? (
          <>
            <p>Local transaction hash</p>
            <p className="mono hash">{execution.transaction_hash}</p>
          </>
        ) : (
          <p>No transaction hash recorded.</p>
        )}
        {["SUBMITTED", "UNCERTAIN", "SUBMITTING"].includes(status) && (
          <button
            onClick={() => reconcile.mutate()}
            disabled={reconcile.isPending}
          >
            Check receipt
          </button>
        )}
        <small className="mono">Proposal {p.id}</small>
      </Panel>
    </>
  );
}
