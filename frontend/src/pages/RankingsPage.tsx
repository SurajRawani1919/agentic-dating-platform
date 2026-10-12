import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";

export function RankingsPage() {
  const participants = useQuery({
    queryKey: ["participants"],
    queryFn: () => api.participants.list(1, 100),
  });
  const demo = useQuery({ queryKey: ["demo"], queryFn: api.demo.get });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-4xl text-ivory-50">Personalized rankings</h1>
        <p className="mt-2 max-w-2xl text-sm text-ivory-300/55">
          Choose a participant to see ranked candidates from persisted evaluations.
          With 25 eligible participants, each person receives rankings for the other 24.
        </p>
      </div>
      {demo.data && (
        <div className="panel p-4 text-sm text-ivory-300/60">
          Active demo run #{demo.data.run.id} · {demo.data.ranking_count} ranking rows ·{" "}
          <StatusBadge label="Synthetic cohort" tone="demo" />
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {(participants.data?.items ?? []).map((p) => (
          <Link
            key={p.id}
            to={`/rankings/${p.id}`}
            className="panel p-5 transition hover:border-champagne-500/30"
          >
            <div className="flex items-center justify-between gap-2">
              <h2 className="font-display text-xl text-ivory-50">{p.display_name}</h2>
              {p.is_synthetic && <StatusBadge label="Synthetic" tone="demo" />}
            </div>
            <p className="mt-2 text-xs text-ivory-300/45">View their ranked matches →</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
