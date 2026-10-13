import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { AuditEvent } from "../../../../packages/shared-types";
import { api } from "../api";
import { ErrorMessage, Panel } from "../components";

export function Audit() {
  const [after, setAfter] = useState(0);
  const query = useQuery({
    queryKey: ["audit", after],
    queryFn: () => api<AuditEvent[]>(`/audit-events?after=${after}`),
  });
  return (
    <>
      <h1>The complete trail.</h1>
      <p className="lede">
        Decisions, approvals, simulations, and chain results in chronological
        order.
      </p>
      <ErrorMessage error={query.error} />
      <Panel title="Audit events">
        {query.data?.map((event) => (
          <details className="audit-event" key={event.id}>
            <summary>
              <span className="event-index">
                {String(event.id).padStart(3, "0")}
              </span>
              <strong>{event.event.replaceAll("_", " ")}</strong>
              <time>{new Date(event.created_at).toLocaleString()}</time>
            </summary>
            <p className="mono">
              Entity: {event.entity_id} · Actor: {event.actor}
            </p>
            <pre>{event.details}</pre>
          </details>
        ))}
        {query.data?.length === 0 && <p>No events on this page.</p>}
        <div className="actions">
          <button className="secondary" onClick={() => setAfter(0)}>
            First page
          </button>
          {query.data?.length === 500 && (
            <button onClick={() => setAfter(query.data?.at(-1)?.id ?? 0)}>
              Next 500 events
            </button>
          )}
        </div>
      </Panel>
    </>
  );
}
