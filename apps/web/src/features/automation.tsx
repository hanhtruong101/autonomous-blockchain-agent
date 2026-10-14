import { ReadinessMessage } from "./readiness";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  AutomationState,
  Policy,
} from "../../../../packages/shared-types";
import { api } from "../api";
import { ErrorMessage, Panel, Status } from "../components";

function timestamp(value: string | null) {
  return value ? new Date(value).toLocaleString() : "—";
}

export function AutomationPanel() {
  const [interval, setInterval] = useState(300);
  const cache = useQueryClient();
  const state = useQuery({
    queryKey: ["automation"],
    queryFn: () => api<AutomationState>("/automation"),
    refetchInterval: 5000,
  });
  const policies = useQuery({
    queryKey: ["policies"],
    queryFn: () => api<Policy[]>("/policies"),
  });
  const active = policies.data?.find((policy) => policy.status === "ACTIVE");
  const action = useMutation({
    mutationFn: (operation: "enable" | "stop" | "freeze" | "resume") =>
      api<AutomationState>(
        `/automation/${operation}`,
        operation === "enable"
          ? { policy_version_id: active?.id, interval_seconds: interval }
          : {},
      ),
    onSettled: () => cache.invalidateQueries(),
  });
  const status = state.data;
  return (
    <Panel title="Automatic portfolio checks">
      <p>
        Enable checks for your approved policy. Low-risk proposals may execute
        with fake assets; medium risk waits for you and high risk is blocked.
        With AI enabled, eligible checks ask it to propose a swap and amount, or
        HOLD. Each proposal must pass independent safety checks. AI cannot
        change permissions or sign.
      </p>
      <ErrorMessage error={state.error ?? policies.error ?? action.error} />
      {state.isPending && <p>Loading automation status…</p>}
      {status && (
        <>
          <Status
            value={
              status.execution_paused
                ? "FROZEN"
                : status.enabled
                  ? "ENABLED"
                  : "STOPPED"
            }
          />
          <ReadinessMessage readiness={status.readiness} />
          <dl>
            <dt>Latest result</dt>
            <dd>{status.last_result}</dd>
            <dt>Last check</dt>
            <dd>{timestamp(status.last_check_at)}</dd>
            <dt>Next check</dt>
            <dd>
              {status.running
                ? "After the current check completes; checks never overlap"
                : timestamp(status.next_check_at)}
            </dd>
            <dt>Current work</dt>
            <dd>
              {status.running || status.generation_in_progress
                ? "Checking portfolio…"
                : "Idle"}
            </dd>
            <dt>Consecutive failures</dt>
            <dd>{status.consecutive_failures} / 3 before freeze</dd>
          </dl>
          {!status.worker_available && (
            <p>Background worker disabled in backend configuration.</p>
          )}
          {active && (
            <p className="muted">
              Approved tolerance: {active.draft.rebalance.tolerance_bps} basis
              points. Policy minimum interval:{" "}
              {active.draft.rebalance.minimum_interval_hours} hours. Checks
              inside tolerance, before that interval or with no remaining budget
              skip trading.
            </p>
          )}
          {active && (
            <p>
              <Link to={`/policies/${active.id}`}>View active policy →</Link>
            </p>
          )}
          <p className="muted">
            Checking every 30 seconds does not authorize a trade every 30
            seconds. The policy interval and budget still apply.
          </p>
          <div className="schedule-field">
            <label htmlFor="check-interval">Check portfolio every</label>
            <select
              id="check-interval"
              value={status.enabled ? status.interval_seconds : interval}
              disabled={status.enabled || action.isPending}
              onChange={(event) => setInterval(Number(event.target.value))}
            >
              <option value={30}>30 seconds · local demonstration</option>
              <option value={300}>5 minutes</option>
              <option value={3600}>1 hour</option>
            </select>
          </div>
          <div className="actions">
            <button
              disabled={
                action.isPending ||
                !active ||
                !status.worker_available ||
                status.enabled ||
                status.running ||
                status.execution_paused ||
                status.generation_in_progress
              }
              onClick={() => action.mutate("enable")}
            >
              Enable for approved policy
            </button>
            <button
              className="secondary"
              disabled={action.isPending || !status.enabled}
              onClick={() => action.mutate("stop")}
            >
              Stop automatic checks
            </button>
            {status.execution_paused ? (
              <button
                disabled={action.isPending}
                onClick={() => action.mutate("resume")}
              >
                Owner: resume execution
              </button>
            ) : (
              <button
                className="danger"
                disabled={action.isPending}
                onClick={() => action.mutate("freeze")}
              >
                Emergency freeze
              </button>
            )}
          </div>
          <p className="muted">
            Freeze cancels unsubmitted proposals and pauses the local smart
            account. Submitted transactions cannot be cancelled. Resume leaves
            automatic checks off. If a check remains stuck after a restart,
            freeze and inspect the audit before resuming.
          </p>
        </>
      )}
    </Panel>
  );
}
