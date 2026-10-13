import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type {
  AutomationState,
  Policy,
  Proposal,
  Wallet,
} from "../../../../packages/shared-types";
import { ReadinessMessage } from "./readiness";
import { api, percent, units } from "../api";
import { ActivityTable, ErrorMessage, Panel } from "../components";

export function Dashboard() {
  const automation = useQuery({
    queryKey: ["automation"],
    queryFn: () => api<AutomationState>("/automation"),
    refetchInterval: 5000,
  });
  const wallet = useQuery({
    queryKey: ["wallet"],
    queryFn: () => api<Wallet>("/wallet/state"),
  });
  const policies = useQuery({
    queryKey: ["policies"],
    queryFn: () => api<Policy[]>("/policies"),
  });
  const activity = useQuery({
    queryKey: ["proposals"],
    queryFn: () => api<Proposal[]>("/proposals"),
  });
  const active = policies.data?.find((policy) => policy.status === "ACTIVE");
  const state = wallet.data;
  const total = state
    ? BigInt(state.usdc_units) + BigInt(state.weth_units)
    : 0n;
  return (
    <>
      <p className="eyebrow">LOCAL CONTROL CENTER</p>
      <h1>Autonomy, within limits.</h1>
      <p className="lede">
        The agent proposes. Your policy decides. Every action leaves a trail.
      </p>
      <ErrorMessage
        error={
          wallet.error ?? policies.error ?? activity.error ?? automation.error
        }
      />
      {automation.data && (
        <Panel title="Agent status">
          <ReadinessMessage readiness={automation.data.readiness} />
          <p>
            Automatic checks: {automation.data.enabled ? "Enabled" : "Stopped"}
          </p>
          <Link to="/activity">Manage checks →</Link>
        </Panel>
      )}
      <div className="stats">
        <Panel title="Test portfolio">
          <strong className="stat">{state ? units(total) : "—"}</strong>
          <p>Fake units · fixed 1:1 test value</p>
        </Panel>
        <Panel title="Spent today">
          <strong className="stat">
            {state ? units(state.spent_units) : "—"}
          </strong>
          <p>
            of {active?.draft.daily_spending_limit.amount ?? "100"} TestUSDC
            equivalent
          </p>
        </Panel>
        <Panel title="Control status">
          <strong className="stat small">
            {active ? "Policy active" : "Approval needed"}
          </strong>
          <p>
            {active
              ? "All proposals are checked before execution."
              : "Create and approve your first policy."}
          </p>
        </Panel>
      </div>
      <div className="columns">
        <Panel title="Wallet allocation">
          {state && (
            <>
              <div className="allocation">
                <span
                  style={{
                    width: `${percent(state.usdc_units, total)}%`,
                  }}
                />
              </div>
              <dl>
                <dt>TestUSDC</dt>
                <dd>
                  {units(state.usdc_units)} · {percent(state.usdc_units, total)}
                  %
                </dd>
                <dt>TestWETH</dt>
                <dd>
                  {units(state.weth_units)} · {percent(state.weth_units, total)}
                  %
                </dd>
              </dl>
              <small className="mono">{state.address}</small>
            </>
          )}
        </Panel>
        <Panel title="Active policy">
          {active ? (
            <>
              <p>{active.goal}</p>
              <Link to={`/policies/${active.id}`}>Review policy →</Link>
            </>
          ) : (
            <>
              <p>Give the agent a clear budget and a defined scope.</p>
              <Link className="button" to="/policies/new">
                Create policy
              </Link>
            </>
          )}
        </Panel>
      </div>
      <Panel title="Recent agent activity">
        <ActivityTable items={activity.data?.slice(0, 5) ?? []} />
      </Panel>
    </>
  );
}
