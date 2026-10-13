import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type {
  Approval,
  Proposal,
  AutomationState,
} from "../../../../packages/shared-types";
import { api, units } from "../api";
import { ErrorMessage, Panel, Status } from "../components";
import { AutomationPanel } from "./automation";
import { CheckHistory } from "./check-history";

export function Activity() {
  const automation = useQuery({
    queryKey: ["automation"],
    queryFn: () => api<AutomationState>("/automation"),
    refetchInterval: 5000,
  });
  const queryClient = useQueryClient();
  const run = useMutation({
    mutationFn: (scenario: string) =>
      api<Proposal | null>("/agent/runs", { scenario }),
    onSuccess: (proposal) => {
      if (proposal) {
        queryClient.setQueryData<Proposal[]>(["proposals"], (items) => [
          proposal,
          ...(items ?? []).filter((item) => item.id !== proposal.id),
        ]);
      }
      return queryClient.invalidateQueries();
    },
  });
  return (
    <>
      <div className="page-heading activity-heading">
        <h1>Agent activity.</h1>
        <Link className="button secondary" to="/proposals">
          View proposals &amp; outcomes
        </Link>
      </div>
      <p className="lede">
        Each eligible check observes the test wallet. AI proposes a swap with
        assets, amount and reasoning, or chooses HOLD. Independent safety checks
        decide whether the proposed trade can execute.
      </p>
      <AutomationPanel />
      <Panel title="Run once">
        <p>
          Ask AI to propose a trade toward your approved target. Its amount is
          preserved for review and may be blocked by policy, simulation or risk
          checks. Offline mode uses a deterministic reference agent.
        </p>
        <button
          disabled={
            run.isPending || automation.data?.readiness.code !== "READY"
          }
          onClick={() => run.mutate("portfolio")}
        >
          {run.isPending ? "Preparing and evaluating…" : "Run portfolio check"}
        </button>
        <p className="muted">
          If this button is unavailable, the status above explains what needs
          attention.
        </p>
        <details>
          <summary>
            Educational safety scenarios (fixed proposals, no AI)
          </summary>
          <p>
            These scenarios can submit fake-money transactions through the same
            safety checks. They are not autonomous model proposals. The 70-unit
            review requires an approved per-trade ceiling of at least 70 and
            sufficient daily budget.
          </p>
          <div className="actions">
            {[
              ["A", "30-unit swap"],
              ["B", "80-unit budget test"],
              ["C", "Unknown contract"],
              ["D", "Excessive slippage"],
              ["medium", "70-unit approval test"],
            ].map(([scenario, label]) => (
              <button
                className="secondary"
                key={scenario}
                disabled={run.isPending || automation.data?.execution_paused}
                onClick={() => run.mutate(scenario)}
              >
                {label}
              </button>
            ))}
          </div>
        </details>
        <ErrorMessage error={run.error} />
        {run.isSuccess && run.data === null && (
          <p role="status">
            No transaction was proposed. Check history below distinguishes an AI
            HOLD from a system skip and explains why.
          </p>
        )}
      </Panel>
      {run.isSuccess && run.data && (
        <div className="run-result" role="status">
          <strong>Your latest run has a result.</strong>
          <Status value={run.data.status} />
          <Link className="button" to={`/transactions/${run.data.id}`}>
            Open this proposal
          </Link>
        </div>
      )}
      <CheckHistory />
      <ProposalResults />
    </>
  );
}

export function ProposalsPage() {
  return (
    <>
      <p className="eyebrow">AGENT RESULTS</p>
      <h1>Proposals &amp; outcomes.</h1>
      <p className="lede">
        See what the agent suggested, which checks passed, and what happened
        next.
      </p>
      <Link className="button" to="/activity">
        Run the agent
      </Link>
      <ProposalResults />
    </>
  );
}

function ProposalResults() {
  const query = useQuery({
    queryKey: ["proposals"],
    queryFn: () => api<Proposal[]>("/proposals"),
    refetchInterval: 5000,
  });
  return (
    <section
      className="proposal-results"
      aria-labelledby="proposal-results-title"
    >
      <div className="page-heading activity-heading">
        <div>
          <p className="eyebrow">REVIEW THE RESULTS</p>
          <h2 id="proposal-results-title">Proposals and outcomes</h2>
        </div>
        <button
          className="secondary"
          disabled={query.isFetching}
          onClick={() => void query.refetch()}
        >
          {query.isFetching ? "Loading…" : "Refresh results"}
        </button>
      </div>
      <p className="muted">
        Newest first. Open a proposal to see the full safety checks, approval
        and transaction hash.
      </p>
      <ErrorMessage error={query.error} />
      {query.isPending && <p role="status">Loading proposals…</p>}
      {query.isSuccess && query.data.length === 0 && (
        <div className="panel results-empty">
          <h3>No proposals yet</h3>
          <p>
            Approve a policy, then open Agent activity and choose Run portfolio
            check. Its results will appear here.
          </p>
          <p className="muted">
            If no trade is needed or permitted yet, readiness explains why and
            no transaction proposal is created.
          </p>
          <Link to="/policies/new">Create a policy</Link> ·{" "}
          <Link to="/audit">Check the audit log</Link>
        </div>
      )}
      {query.data?.map((item) => (
        <article className="panel proposal-card" key={item.id}>
          <div className="page-heading activity-heading">
            <p className="eyebrow">
              {item.generation?.execution_mode === "ai_trade_proposal"
                ? "AI trade proposal ·"
                : item.generation?.execution_mode ===
                    "ai_decision_deterministic_sizing"
                  ? "AI decision · calculated amount ·"
                  : item.generation?.execution_mode ===
                      "deterministic_with_ai_explanation"
                    ? "Calculated trade · explanation by"
                    : "Source:"}{" "}
              {item.generation?.provider ?? "Not recorded"}{" "}
              {item.generation?.model ?? ""}
            </p>
            <Status value={item.status} />
          </div>
          <h3>
            Swap {units(item.proposal.amount)} {item.proposal.asset_in} →{" "}
            {item.proposal.asset_out}
          </h3>
          <p>{item.proposal.reason}</p>
          <div className="proposal-checks">
            <div>
              <span>Policy</span>
              <Status
                value={
                  item.evaluation
                    ? item.evaluation.policy.allowed
                      ? "PASS"
                      : "BLOCKED"
                    : "PENDING"
                }
              />
            </div>
            <div>
              <span>Simulation</span>
              <Status
                value={
                  item.evaluation
                    ? item.evaluation.simulation.success
                      ? "PASS"
                      : "BLOCKED"
                    : "PENDING"
                }
              />
            </div>
            <div>
              <span>Risk</span>
              <Status value={item.evaluation?.risk.level ?? "PENDING"} />
            </div>
          </div>
          <p className="muted">
            {item.status === "AWAITING_APPROVAL"
              ? "Waiting for your approval. Review the exact proposal before deciding."
              : item.status === "BLOCKED"
                ? "Blocked by safety checks. Open the proposal to see why."
                : item.status === "EXECUTED"
                  ? "Confirmed on the local blockchain. The transaction hash is in the details."
                  : "Open the proposal to inspect its current execution status."}
          </p>
          <div className="page-heading activity-heading">
            <time className="muted" dateTime={item.proposal.created_at}>
              {new Date(item.proposal.created_at).toLocaleString()}
            </time>
            <Link className="button" to={`/transactions/${item.id}`}>
              {item.status === "AWAITING_APPROVAL"
                ? "Review and decide"
                : "View proposal details"}
            </Link>
          </div>
        </article>
      ))}
    </section>
  );
}

export function Approvals() {
  const query = useQuery({
    queryKey: ["approvals"],
    queryFn: () => api<Approval[]>("/approvals"),
  });
  return (
    <>
      <h1>Your approval queue.</h1>
      <p className="lede">
        Medium-risk proposals need your review. Approval expires after ten
        minutes.
      </p>
      <ErrorMessage error={query.error} />
      <Panel title="Review requests">
        {query.data?.length === 0 && <p>No approval requests.</p>}
        {query.data?.map((item) => (
          <div className="queue-item" key={item.id}>
            <div>
              <Status value={item.status} />
              <p>Expires {new Date(item.expires_at).toLocaleString()}</p>
            </div>
            <Link to={`/transactions/${item.proposal_id}`}>
              Review transaction →
            </Link>
          </div>
        ))}
      </Panel>
    </>
  );
}
