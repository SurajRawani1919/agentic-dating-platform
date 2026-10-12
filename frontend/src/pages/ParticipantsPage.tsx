import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";

export function ParticipantsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["participants"],
    queryFn: () => api.participants.list(1, 100),
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-4xl text-ivory-50">Participants</h1>
        <p className="mt-2 text-sm text-ivory-300/55">
          Directory of consenting participants. Synthetic demo profiles are labeled.
        </p>
      </div>
      {isLoading && <p className="animate-pulse-soft text-sm text-ivory-300/50">Loading…</p>}
      {error && <p className="text-sm text-amber-300">{(error as Error).message}</p>}
      <div className="grid gap-3 sm:grid-cols-2">
        {(data?.items ?? []).map((p) => (
          <Link
            key={p.id}
            to={`/participants/${p.id}`}
            className="panel block p-5 transition hover:border-champagne-500/30"
          >
            <div className="flex items-start justify-between gap-3">
              <h2 className="font-display text-2xl text-ivory-50">{p.display_name}</h2>
              <div className="flex flex-col items-end gap-1">
                {p.is_synthetic ? (
                  <StatusBadge label="Synthetic demo" tone="demo" />
                ) : (
                  <StatusBadge label="Submitted" tone="neutral" />
                )}
                <StatusBadge label={p.source_verification_status} />
              </div>
            </div>
            <p className="mt-3 text-xs text-ivory-300/45">
              Consent: {p.consent_status} · Analysis: {p.has_analysis ? "yes" : "pending"}
            </p>
          </Link>
        ))}
      </div>
      {!isLoading && !data?.items.length && (
        <p className="text-sm text-ivory-300/40">
          Empty directory. <Link className="text-champagne-400" to="/demo">Load demo</Link> or{" "}
          <Link className="text-champagne-400" to="/app">add a participant</Link>.
        </p>
      )}
    </div>
  );
}
