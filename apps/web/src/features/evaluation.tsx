import { useQuery } from "@tanstack/react-query";
import type {
  EvaluationReport,
  EvaluationView,
} from "../../../../packages/shared-types";
import { api, units } from "../api";
import { ErrorMessage, Panel, Status } from "../components";

export function EvaluationPage() {
  const query = useQuery({
    queryKey: ["evaluation"],
    queryFn: () => api<EvaluationView>("/evaluation"),
    refetchInterval: false,
  });
  return (
    <>
      <h1>Agent evaluation.</h1>
      <p className="lede">
        Compare AI trade proposals with a deterministic reference and inspect
        safety outcomes. This page cannot sign or submit transactions.
      </p>
      <ErrorMessage error={query.error} />
      <button
        className="secondary"
        disabled={query.isFetching}
        onClick={() => void query.refetch()}
      >
        Refresh reports
      </button>
      {query.isPending && <p>Loading evaluation…</p>}
      {query.data && (
        <>
          <Report report={query.data.deterministic} />
          <Panel title="Optional Ollama shadow comparison">
            <p>{query.data.shadow_status}</p>
            <p>From the project root, using your installed model, run:</p>
            <pre>
              uv run python scripts/evaluate_agent.py --ollama-model
              llama3:latest
            </pre>
            <p>
              The command only requests AI trade proposals for synthetic
              snapshots. It does not touch your policy, wallet or schedule.
              Refresh this page when it finishes.
            </p>
          </Panel>
          {query.data.ollama_shadow && (
            <Report report={query.data.ollama_shadow} />
          )}
        </>
      )}
    </>
  );
}

function Report({ report }: { report: EvaluationReport }) {
  return (
    <Panel
      title={
        report.provider === "deterministic"
          ? "Deterministic sizing baseline"
          : "Ollama trade proposals — observation only"
      }
    >
      <p>
        <strong>
          {report.decision_matches}/{report.decision_cases}
        </strong>{" "}
        trade/no-trade agreements with the scenario expectation ·{" "}
        <strong>
          {report.sizing_matches}/{report.sizing_cases}
        </strong>{" "}
        proposed trade matches with the reference
      </p>
      <p className="muted">
        Action agreement compares trading with HOLD; direction and amount are
        compared separately against the reference. HOLD can be safe yet delay
        progress. A mismatch is not automatically a safety violation. No sizing
        test is counted when AI chooses HOLD. The benchmark also calls AI on
        snapshots the live preflight would skip, to test its understanding. A
        smaller permitted trade can differ from the reference without being
        unsafe. Historical bounded-decision reports are not loaded here.
      </p>
      <p>
        {report.model ?? "Integer calculations"} ·{" "}
        {new Date(report.created_at).toLocaleString()}
      </p>
      <p>
        <strong>
          {report.correct}/{report.total}
        </strong>{" "}
        complete plan matches · {report.invalid_outputs} invalid outputs ·{" "}
        {report.total_latency_ms} ms total
      </p>
      <p>
        {report.proposed_trades} proposed trades · {report.approval_requests}{" "}
        approval requests · {report.blocked} blocked results
      </p>
      <p className="muted">
        {report.limitation} Latency depends on hardware and model loading. A
        deliberately reverting simulation should be blocked even when sizing is
        correct. Compare the same scenario rows if report sizes differ.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Scenario</th>
              <th>Expected</th>
              <th>Proposed</th>
              <th>Trade / HOLD decision</th>
              <th>Trade vs reference</th>
              <th>Safety decision</th>
            </tr>
          </thead>
          <tbody>
            {report.rows.map((row) => (
              <tr key={row.scenario}>
                <td>
                  {row.scenario}
                  {row.error && <p>{row.error}</p>}
                </td>
                <td>
                  {row.expected_action} · {units(row.expected_amount_units)}
                </td>
                <td>
                  {row.actual_action} · {units(row.actual_amount_units)}
                </td>
                <td>
                  {row.agent_action ?? "INVALID"} ·{" "}
                  {row.decision_matches_expected === null
                    ? "Unavailable"
                    : row.decision_matches_expected
                      ? "Matches"
                      : "Differs"}
                </td>
                <td>
                  {row.sizing_matches_expected === null
                    ? "Not evaluated"
                    : row.sizing_matches_expected
                      ? "Matches"
                      : "Differs"}
                </td>
                <td>
                  <Status value={row.decision} />
                  {row.safety_violations.length > 0 && (
                    <p>{row.safety_violations.join(", ")}</p>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
