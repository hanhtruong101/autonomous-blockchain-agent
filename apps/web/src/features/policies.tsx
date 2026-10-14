import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import type { Configuration, Policy } from "../../../../packages/shared-types";
import { api } from "../api";
import { ErrorMessage, Panel, Status } from "../components";

const example =
  "Keep approximately 70% of my portfolio in USDC, never spend more than 100 USDC per day, rebalance weekly, and only interact with approved protocols.";
export function CreatePolicy() {
  const [goal, setGoal] = useState(example);
  const [tolerance, setTolerance] = useState(100);
  const [maximumTrade, setMaximumTrade] = useState("30");
  const [minimum, setMinimum] = useState("");
  const navigate = useNavigate();
  const configuration = useQuery({
    queryKey: ["configuration"],
    queryFn: () => api<Configuration>("/configuration"),
  });
  const mutation = useMutation({
    mutationFn: () =>
      api<Policy>("/policies", {
        goal,
        tolerance_bps: tolerance,
        maximum_trade_amount: maximumTrade,
        minimum_usdc_ratio:
          minimum === ""
            ? null
            : `${BigInt(minimum) / 100n}.${(BigInt(minimum) % 100n).toString().padStart(2, "0")}`,
      }),
    onSuccess: (policy) => navigate(`/policies/${policy.id}`),
  });
  return (
    <div className="policy-create">
      <h1>Create a policy.</h1>
      <p className="lede">
        Your goal becomes a draft. Only your explicit approval can activate it.
      </p>
      <Panel title="What should the agent do?">
        <form
          className="policy-form"
          onSubmit={(event) => {
            event.preventDefault();
            mutation.mutate();
          }}
        >
          <label htmlFor="goal">Portfolio goal</label>
          <textarea
            id="goal"
            rows={4}
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
            maxLength={2000}
          />
          <p className="muted">
            {configuration.data?.interpreter === "llm"
              ? `Model enabled: creating a draft sends this goal to ${configuration.data.provider_host}. Review the interpretation carefully; the model cannot activate it.`
              : "Offline interpreter: use this template. Change the percentage, daily limit (up to 100), and cadence to weekly, daily, or on demand. No external AI service is called."}
          </p>
          <fieldset className="policy-boundaries">
            <legend>Trading boundaries</legend>
            <div className="policy-fields">
              <div className="policy-field policy-field-wide">
                <label htmlFor="tolerance">
                  Accepted deviation from target
                </label>
                <select
                  id="tolerance"
                  aria-describedby="tolerance-help"
                  value={tolerance}
                  onChange={(event) => setTolerance(Number(event.target.value))}
                >
                  <option value={0}>Exact target</option>
                  <option value={100}>±1 percentage point</option>
                  <option value={500}>±5 percentage points</option>
                </select>
                <p className="muted" id="tolerance-help">
                  For example, a 95% target with ±1 point accepts 94–96%. This
                  is a target band, not a hard minimum.
                </p>
              </div>
              <div className="policy-field">
                <label htmlFor="minimum-usdc">
                  Minimum USDC share (%) · optional
                </label>
                <input
                  id="minimum-usdc"
                  aria-describedby="minimum-help"
                  type="number"
                  min="0"
                  max="100"
                  step="1"
                  value={minimum}
                  onChange={(event) => setMinimum(event.target.value)}
                  placeholder="No additional minimum"
                />
                <p className="muted" id="minimum-help">
                  Every simulated trade must finish at or above this share. A
                  stricter minimum in your goal is preserved. If your wallet
                  starts below it, a small trade may be blocked.
                </p>
              </div>
              <div className="policy-field">
                <label htmlFor="maximum-trade">
                  Maximum per trade (TestUSDC equivalent)
                </label>
                <input
                  id="maximum-trade"
                  aria-describedby="trade-help"
                  type="number"
                  min="0.000001"
                  max="100"
                  step="0.000001"
                  required
                  value={maximumTrade}
                  onChange={(event) => setMaximumTrade(event.target.value)}
                />
                <p className="muted" id="trade-help">
                  AI can propose an amount, but independent checks enforce this
                  ceiling and the daily budget. These form settings are included
                  in the draft for your review.
                </p>
              </div>
            </div>
          </fieldset>
          <div className="policy-form-footer">
            <p className="muted">
              Review the draft before approving. Creating it does not start
              trading.
            </p>
            <button disabled={mutation.isPending || !configuration.data}>
              {mutation.isPending ? "Creating draft…" : "Create policy draft"}
            </button>
          </div>
          <ErrorMessage error={mutation.error ?? configuration.error} />
        </form>
      </Panel>
    </div>
  );
}

export function PolicyReview() {
  const { id } = useParams();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["policy", id],
    queryFn: () => api<Policy>(`/policies/${id}`),
  });
  const approve = useMutation({
    mutationFn: () => api<Policy>(`/policies/${id}/approve`, {}),
    onSuccess: (policy) => {
      queryClient.setQueryData(["policy", id], policy);
      return queryClient.invalidateQueries();
    },
  });
  if (!query.data)
    return (
      <>
        <h1>Policy review</h1>
        <ErrorMessage error={query.error} />
        <p>Loading draft…</p>
      </>
    );
  const { draft, status } = query.data;
  return (
    <>
      <div className="page-heading">
        <h1>
          {status === "ACTIVE" ? "Your active policy." : "Review your policy."}
        </h1>
        <Status value={status} />
      </div>
      <Link to="/policies">← All policies</Link>
      <p className="lede">
        {status === "ACTIVE"
          ? "This approved version governs agent proposals. Automatic checks must be enabled separately in Agent activity."
          : status === "DRAFT"
            ? "Read these restrictions before granting the agent permission."
            : "This historical version is no longer active."}
      </p>
      {approve.isSuccess && status === "ACTIVE" && (
        <p role="status">
          Policy approved and saved. You can return to it anytime from Policies.
        </p>
      )}
      <Panel title="Original goal">
        <p>{query.data.goal}</p>
        <p className="muted">
          Created {new Date(query.data.created_at).toLocaleString()}
        </p>
        <p className="mono">Version: {query.data.id}</p>
      </Panel>
      <Panel title="Interpreted boundaries">
        <dl>
          <dt>Daily spending ceiling</dt>
          <dd>{draft.daily_spending_limit.amount} TestUSDC equivalent</dd>
          <dt>Portfolio target</dt>
          <dd>
            USDC {query.data.target_usdc_percent}% / WETH{" "}
            {query.data.target_weth_percent}%
          </dd>
          <dt>Accepted USDC target range</dt>
          <dd>{query.data.accepted_usdc_range}</dd>
          <dt>Hard minimum USDC allocation</dt>
          <dd>
            {query.data.minimum_usdc_percent === null
              ? "Not configured"
              : `${query.data.minimum_usdc_percent}% after every trade`}
          </dd>
          <dt>Maximum per trade</dt>
          <dd>{draft.maximum_trade_amount} TestUSDC equivalent</dd>
          <dt>Minimum time between completed trades</dt>
          <dd>{draft.rebalance.minimum_interval_hours} hours</dd>
          <dt>Rebalance tolerance</dt>
          <dd>{draft.rebalance.tolerance_bps} basis points around target</dd>
          <dt>Maximum slippage</dt>
          <dd>{draft.maximum_slippage_bps} basis points</dd>
          <dt>Protocols</dt>
          <dd>{draft.allowed_protocols.join(", ")}</dd>
          <dt>Allowed contracts</dt>
          <dd className="mono">{draft.allowed_contracts.join(", ")}</dd>
        </dl>
        <details>
          <summary>Structured policy</summary>
          <pre>{JSON.stringify(draft, null, 2)}</pre>
        </details>
        <p>
          The check schedule is configured separately in Agent activity. The
          optional allocation minimum is enforced off-chain against simulation;
          the contract independently enforces spending, allowed targets and
          pause controls. Changes create a new version and require another
          approval. The on-chain ceiling remains 100 test units per UTC day.
        </p>
        {status === "DRAFT" ? (
          <button disabled={approve.isPending} onClick={() => approve.mutate()}>
            Approve and activate this policy
          </button>
        ) : (
          <Link className="button" to="/activity">
            Open agent activity
          </Link>
        )}
        <ErrorMessage error={approve.error} />
      </Panel>
    </>
  );
}

export function Policies() {
  const query = useQuery({
    queryKey: ["policies"],
    queryFn: () => api<Policy[]>("/policies"),
  });
  const active = query.data?.find((policy) => policy.status === "ACTIVE");
  const history = query.data?.filter((policy) => policy.status !== "ACTIVE");
  return (
    <>
      <div className="page-heading activity-heading">
        <h1>Your policies.</h1>
        <Link className="button" to="/policies/new">
          Create policy
        </Link>
      </div>
      <p className="lede">
        Approved policies stay here. ACTIVE means the version is in effect;
        automatic checks are enabled separately in Agent activity.
      </p>
      <ErrorMessage error={query.error} />
      {query.isPending && <p role="status">Loading policies…</p>}
      {query.isSuccess && (
        <>
          <Panel title="Active policy">
            {active ? (
              <PolicySummary policy={active} />
            ) : (
              <p>
                No approved policy is active yet. Review and approve a draft
                below.
              </p>
            )}
          </Panel>
          <Panel title="Drafts and previous versions">
            {history?.length === 0 && <p>No drafts or previous versions.</p>}
            {history?.map((policy) => (
              <article className="queue-item" key={policy.id}>
                <PolicySummary policy={policy} />
              </article>
            ))}
          </Panel>
        </>
      )}
    </>
  );
}

function PolicySummary({ policy }: { policy: Policy }) {
  return (
    <div>
      <Status value={policy.status} />
      <p>{policy.goal}</p>
      <p className="muted">
        Daily ceiling: {policy.draft.daily_spending_limit.amount} TestUSDC
        equivalent · Minimum interval:{" "}
        {policy.draft.rebalance.minimum_interval_hours} hours
      </p>
      <p className="muted">
        Created {new Date(policy.created_at).toLocaleString()}
      </p>
      <Link to={`/policies/${policy.id}`}>
        {policy.status === "DRAFT" ? "Review draft" : "View policy details"} →
      </Link>
    </div>
  );
}
