import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { Proposal } from "../../../packages/shared-types";
import { units } from "./api";

export function Status({ value }: { value: string }) {
  return (
    <span
      className={`status ${["BLOCKED", "HIGH", "FAILED", "UNCERTAIN", "REJECTED"].includes(value) ? "bad" : ["ACTIVE", "EXECUTED", "LOW", "PASS"].includes(value) ? "good" : ""}`}
    >
      {value.replaceAll("_", " ")}
    </span>
  );
}
export function ErrorMessage({ error }: { error: Error | null }) {
  return error ? (
    <p role="alert" className="error">
      {error.message}
    </p>
  ) : null;
}
export function Panel({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {children}
    </section>
  );
}
export function ActivityTable({ items }: { items: Proposal[] }) {
  return items.length === 0 ? (
    <p className="muted">
      No proposals yet. Approve a policy, then run the agent.
    </p>
  ) : (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Action</th>
            <th>Amount</th>
            <th>Risk</th>
            <th>Result</th>
            <th>Review</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                {item.proposal.asset_in} → {item.proposal.asset_out}
                <small>{item.proposal.protocol}</small>
              </td>
              <td>{units(item.proposal.amount)}</td>
              <td>
                <Status value={item.evaluation?.risk.level ?? "PENDING"} />
              </td>
              <td>
                <Status value={item.status} />
              </td>
              <td>
                <Link to={`/transactions/${item.id}`}>View details →</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
