import { Link } from "react-router-dom";
import { usePeople } from "../api/hooks";
import { SampleNotice } from "../components/SampleNotice";
import { StatusBadge } from "../components/StatusBadge";

export function ParticipantsPage() {
  const { data, isLoading, error } = usePeople();
  const items = data?.items ?? [];

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-4xl text-ivory-50">Profiles</h1>
          <p className="mt-2 text-sm text-ivory-300/55">
            {items.length} {items.length === 1 ? "person" : "people"}, each read from a LinkedIn
            and a public Instagram. Open one to see what their agent found.
          </p>
        </div>
        <Link className="btn-primary" to="/app">
          Add people
        </Link>
      </div>
      {data?.isSample && <SampleNotice />}
      {isLoading && <p className="animate-pulse-soft text-sm text-ivory-300/50">Loading…</p>}
      {error && <p className="text-sm text-amber-300">{(error as Error).message}</p>}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((p) => (
          <Link
            key={p.id}
            to={`/participants/${p.id}`}
            className="panel block p-5 transition hover:border-champagne-500/30"
          >
            <div className="flex items-start justify-between gap-3">
              <h2 className="font-display text-2xl text-ivory-50">{p.display_name}</h2>
              {p.is_synthetic ? (
                <StatusBadge label="Synthetic" tone="warn" />
              ) : (
                <StatusBadge
                  label={p.has_analysis ? "Analyzed" : "Pending"}
                  tone={p.has_analysis ? "good" : "warn"}
                />
              )}
            </div>
            <p className="mt-2 line-clamp-2 min-h-[2.5rem] text-sm text-ivory-300/55">
              {p.headline || "Open to see the analysis"}
            </p>
            <p className="mt-3 text-xs text-ivory-300/35">
              {p.sources
                .map((s) => `${s.source_type}: ${s.acquisition_status.replace(/_/g, " ")}`)
                .join(" · ")}
            </p>
          </Link>
        ))}
      </div>
      {!isLoading && !items.length && (
        <p className="text-sm text-ivory-300/40">
          Nobody here yet. <Link className="text-champagne-400" to="/app">Add people</Link> by
          pasting their links.
        </p>
      )}
    </div>
  );
}
