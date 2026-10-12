import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";

export function DemoPage() {
  const qc = useQueryClient();
  const demo = useQuery({ queryKey: ["demo"], queryFn: api.demo.get });
  const reseed = useMutation({
    mutationFn: api.demo.seed,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["demo"] });
      qc.invalidateQueries({ queryKey: ["participants"] });
    },
  });

  if (demo.isLoading) return <p className="animate-pulse-soft text-sm text-ivory-300/50">Loading demo…</p>;
  if (demo.error) return <p className="text-amber-300">{(demo.error as Error).message}</p>;
  const d = demo.data!;

  const shareUrl = `${window.location.origin}/demo`;

  return (
    <div className="space-y-8">
      <div className="panel overflow-hidden">
        <div className="border-b border-champagne-500/30 bg-champagne-500/10 px-6 py-3 text-xs uppercase tracking-[0.2em] text-champagne-400">
          {d.label}
        </div>
        <div className="px-6 py-8">
          <h1 className="font-display text-4xl text-ivory-50">Saved demonstration run</h1>
          <p className="mt-3 max-w-2xl text-sm text-ivory-300/60">
            Inspect 25 synthetic participants, example agent conversations, and complete personalized
            rankings without an API key. Synthetic profiles are never marked as verified real people.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link className="btn-primary" to={`/participants/${d.first_participant_id}`}>
              Browse a profile
            </Link>
            <Link className="btn-ghost" to={`/dates/${d.showcase_date_ids[0] ?? ""}`}>
              Watch example date
            </Link>
            <Link className="btn-ghost" to={`/rankings/${d.first_participant_id}`}>
              Inspect rankings
            </Link>
            <button className="btn-ghost" type="button" onClick={() => reseed.mutate()} disabled={reseed.isPending}>
              {reseed.isPending ? "Reseeding…" : "Reseed demo"}
            </button>
          </div>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Participants", d.synthetic_participant_count],
          ["Date sessions", d.session_count],
          ["Ranking rows", d.ranking_count],
          ["Run status", d.run.status],
        ].map(([label, value]) => (
          <div key={String(label)} className="panel p-5">
            <div className="text-[11px] uppercase tracking-[0.16em] text-ivory-300/45">{label}</div>
            <div className="mt-2 font-display text-3xl text-ivory-50">{value}</div>
          </div>
        ))}
      </div>

      <div className="panel p-6">
        <h2 className="font-display text-2xl text-ivory-50">Demo notes</h2>
        <ul className="mt-4 space-y-2 text-sm text-ivory-200/70">
          {d.notes.map((n) => (
            <li key={n} className="flex gap-2">
              <StatusBadge label="Note" tone="demo" />
              <span>{n}</span>
            </li>
          ))}
        </ul>
        <div className="mt-6">
          <label className="label">Stable demo URL</label>
          <div className="flex flex-wrap gap-2">
            <input className="field" readOnly value={shareUrl} />
            <button
              className="btn-ghost"
              type="button"
              onClick={() => navigator.clipboard.writeText(shareUrl)}
            >
              Copy
            </button>
          </div>
        </div>
      </div>

      <div>
        <h2 className="font-display text-2xl text-ivory-50">Showcase conversations</h2>
        <div className="mt-4 flex flex-wrap gap-2">
          {d.showcase_date_ids.map((id) => (
            <Link key={id} className="btn-ghost" to={`/dates/${id}`}>
              Date #{id}
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
