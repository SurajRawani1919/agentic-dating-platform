import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { usePeople } from "../api/hooks";
import { SampleNotice } from "../components/SampleNotice";
import { StatusBadge } from "../components/StatusBadge";

export function RankingsPage() {
  const participants = usePeople();
  const demo = useQuery({ queryKey: ["demo"], queryFn: api.demo.get });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-4xl text-ivory-50">Personalized rankings</h1>
        <p className="mt-2 max-w-2xl text-sm text-ivory-300/55">
          Choose a person to see who fits them best. Every ranking is personal: it leans on
          the verdict of that person's own agent after each date.
        </p>
      </div>
      {participants.data?.isSample && <SampleNotice />}
      {demo.data && (
        <div className="panel p-4 text-sm text-ivory-300/60">
          Run #{demo.data.run.id} · {demo.data.participant_count} people ·{" "}
          {demo.data.ranking_count} ranking rows
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
              {p.is_synthetic && <StatusBadge label="Synthetic" tone="warn" />}
            </div>
            <p className="mt-2 text-xs text-ivory-300/45">
              {(() => {
                const top = demo.data?.top_matches.find((m) => m.participant_id === p.id);
                return top ? `Best fit: ${top.candidate_name} (${top.score.toFixed(1)}) →` : "See who fits them best →";
              })()}
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
