import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type { AgentActivityView } from "../../../../packages/shared-types";
import { api, units } from "../api";
import { ErrorMessage, Panel, Status } from "../components";

export function CheckHistory() {
  const query = useQuery({
    queryKey: ["agent-activity"],
    queryFn: () => api<AgentActivityView>("/agent/activity"),
    refetchInterval: 5000,
  });
  return (
    <Panel title="Check history">
      <p>
        The latest 50 checks include system skips and AI HOLD decisions, even
        when no transaction exists. Older runs remain in Audit log. This
        detailed history starts with the bounded-decision update.
      </p>
      <ErrorMessage error={query.error} />
      {query.isPending && <p role="status">Loading check history…</p>}
      {query.data && query.data.consecutive_ai_holds >= 3 && (
        <p role="status">
          AI chose HOLD on {query.data.consecutive_ai_holds} consecutive
          eligible checks in this history window. Review its reasons and the
          approved goal. This is an advisory, not permission to bypass the model
          or safety checks.
        </p>
      )}
      {query.data?.items.length === 0 && (
        <p>
          No checks recorded yet. Run once or enable automatic checks when
          ready.
        </p>
      )}
      {query.data?.items.map((item, index) => (
        <details key={item.id} open={index === 0} className="panel">
          <summary>
            <Status value={item.proposal_status ?? item.state} /> ·{" "}
            {item.source} · {new Date(item.updated_at).toLocaleString()}
          </summary>
          <p>{item.reason}</p>
          {item.generation && (
            <p className="muted">
              Source: {item.generation.provider} {item.generation.model ?? ""}
            </p>
          )}
          <ol>
            <li>
              <strong>Observation:</strong>{" "}
              {item.observation
                ? `${units(item.observation.usdc_units)} USDC / ${units(item.observation.weth_units)} WETH; ${units(item.observation.spent_units)} test units spent today.`
                : "No wallet snapshot recorded."}
            </li>
            <li>
              <strong>AI decision:</strong>{" "}
              {item.decision
                ? `${item.decision.action} — ${item.decision.reason}`
                : item.state === "SYSTEM_SKIPPED"
                  ? "Not called: the system skipped this check."
                  : item.generation?.provider === "offline" ||
                      item.source === "fixture"
                    ? "No AI: deterministic calculation or fixed test scenario."
                    : "No accepted decision yet. Failed or interrupted runs never receive fallback execution."}
            </li>
            <li>
              <strong>
                {item.generation?.execution_mode === "ai_trade_proposal"
                  ? "AI trade proposal:"
                  : "Calculated plan:"}
              </strong>{" "}
              {item.calculation ?? "No executable transaction plan stored."}
            </li>
            <li>
              <strong>Safety checks:</strong>{" "}
              {item.proposal_id ? (
                <Link to={`/transactions/${item.proposal_id}`}>
                  Open policy, simulation, risk and approval results →
                </Link>
              ) : (
                "No transaction submitted to the execution pipeline."
              )}
            </li>
            <li>
              <strong>Result:</strong>{" "}
              {(item.proposal_status ?? item.state).replaceAll("_", " ")}
            </li>
          </ol>
          {item.policy_version_id && (
            <Link to={`/policies/${item.policy_version_id}`}>
              Review the policy used for this check →
            </Link>
          )}
        </details>
      ))}
    </Panel>
  );
}
