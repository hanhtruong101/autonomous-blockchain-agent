import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { Readiness } from "../../../../packages/shared-types";
import { Status } from "../components";

export function ReadinessMessage({ readiness }: { readiness: Readiness }) {
  const [clock, setClock] = useState(Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setClock(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const elapsed = readiness.generation_started_at
    ? Math.max(
        0,
        Math.floor(
          (clock - Date.parse(readiness.generation_started_at)) / 1000,
        ),
      )
    : null;
  return (
    <div role="status">
      <Status value={readiness.code} />
      <p>
        <strong>{readiness.reason}</strong>
      </p>
      <p>{readiness.next_step}</p>
      {readiness.eligible_after && (
        <p>
          Eligible after: {new Date(readiness.eligible_after).toLocaleString()}{" "}
          (chain time)
        </p>
      )}
      {elapsed !== null && (
        <p>
          Preparation started{" "}
          {new Date(readiness.generation_started_at!).toLocaleTimeString()} ·
          elapsed {elapsed} seconds.
        </p>
      )}
      {readiness.proposal_id && (
        <Link to={`/transactions/${readiness.proposal_id}`}>
          Open the proposal that needs attention →
        </Link>
      )}
      {readiness.code === "NO_POLICY" && (
        <Link to="/policies/new">Create a policy →</Link>
      )}
      {readiness.code === "UNAVAILABLE" && (
        <Link to="/audit">Inspect recent events →</Link>
      )}
    </div>
  );
}
