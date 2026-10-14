import { useState } from "react";
import { createRoot } from "react-dom/client";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import type { Configuration } from "../../../packages/shared-types";
import { api, setToken } from "./api";
import { Dashboard } from "./features/dashboard";
import { CreatePolicy, PolicyReview, Policies } from "./features/policies";
import { Activity, Approvals, ProposalsPage } from "./features/activity";
import { TransactionDetail } from "./features/detail";
import { Audit } from "./features/audit";
import "./style.css";

const client = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchInterval: 15000 } },
});
function ModeGuide() {
  const query = useQuery({
    queryKey: ["configuration"],
    queryFn: () => api<Configuration>("/configuration"),
  });
  return (
    <section className="panel">
      <strong>
        AI Mode:{" "}
        {query.data
          ? query.data.generation.provider !== "offline"
            ? `${query.data.generation.provider === "ollama" ? "Ollama (local)" : "OpenAI"} · ${query.data.generation.model}`
            : "Offline / Deterministic"
          : "Unavailable"}
      </strong>
      <p>
        AI interprets goals and proposes trades, including direction and amount,
        or chooses HOLD. Independent policy, simulation, risk and smart-account
        controls govern execution.
      </p>
      <p className="muted">
        Local demo only · Fake TestUSDC/TestWETH · No real wallet or funds.
      </p>
      <details>
        <summary>How to use this demo</summary>
        <ol>
          <li>Describe your financial goal.</li>
          <li>Review the generated policy.</li>
          <li>Approve the policy.</li>
          <li>Check readiness, then run once or enable automatic checks.</li>
          <li>
            Inspect Check history, including HOLD decisions and system skips.
          </li>
          <li>Review policy, simulation and risk results.</li>
          <li>Approve medium-risk actions if required.</li>
          <li>Verify the transaction and audit trail.</li>
        </ol>
        <p>
          Scenario A-D and medium buttons are fixed educational fixtures,
          independent of AI mode. Portfolio runs use the selected provider.
        </p>
      </details>
    </section>
  );
}
function App() {
  const [connected, setConnected] = useState(false);
  const [token, setInput] = useState("");
  const [error, setError] = useState("");
  return (
    <BrowserRouter>
      <div className="shell">
        <aside>
          <div className="brand">
            <span className="brand-mark">◈</span> Controlled
            <br />
            <span>Autonomy</span>
          </div>
          <p className="nav-label">WORKSPACE</p>
          <nav>
            {[
              ["/", "Overview"],
              ["/policies", "Policies"],
              ["/policies/new", "Create policy"],
              ["/activity", "Agent activity"],
              ["/proposals", "Proposals & outcomes"],
              ["/approvals", "Approval queue"],
              ["/audit", "Audit log"],
            ].map(([to, label]) => (
              <NavLink end={to === "/" || to === "/policies"} key={to} to={to}>
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="local-badge">
            <span className="dot" /> Local Anvil
            <p>
              Chain 31337 · Test assets only
              <br />
              No real cryptocurrency
            </p>
          </div>
        </aside>
        <div className="workspace">
          <header>
            <span>Policy-controlled portfolio agent</span>
            <span className="test-label">EDUCATIONAL PROTOTYPE</span>
          </header>
          <main>
            {connected ? (
              <>
                <ModeGuide />
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/policies" element={<Policies />} />
                  <Route path="/policies/new" element={<CreatePolicy />} />
                  <Route path="/policies/:id" element={<PolicyReview />} />
                  <Route path="/activity" element={<Activity />} />
                  <Route path="/proposals" element={<ProposalsPage />} />
                  <Route path="/approvals" element={<Approvals />} />
                  <Route
                    path="/transactions/:id"
                    element={<TransactionDetail />}
                  />
                  <Route path="/audit" element={<Audit />} />
                  <Route path="*" element={<p>Page not found.</p>} />
                </Routes>
              </>
            ) : (
              <div className="login">
                <p className="eyebrow">OWNER ACCESS</p>
                <h1>
                  A clear boundary
                  <br />
                  for every action.
                </h1>
                <p>
                  Enter the local owner token configured when starting the
                  application. It stays in memory for this session.
                </p>
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    setToken(token);
                    void api("/wallet/state")
                      .then(() => {
                        setConnected(true);
                        setInput("");
                      })
                      .catch((err: unknown) =>
                        setError(
                          err instanceof Error
                            ? err.message
                            : "Connection failed",
                        ),
                      );
                  }}
                >
                  <label htmlFor="token">Local owner token</label>
                  <input
                    id="token"
                    type="password"
                    value={token}
                    onChange={(event) => setInput(event.target.value)}
                    autoComplete="off"
                    required
                  />
                  <button>Open local workspace</button>
                  {error && (
                    <p role="alert" className="error">
                      {error}
                    </p>
                  )}
                </form>
                <p className="muted">
                  0 real ETH · 0 real USDC · Disposable development accounts
                </p>
              </div>
            )}
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}
createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={client}>
    <App />
  </QueryClientProvider>,
);
