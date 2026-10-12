import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { DemoVideo } from "../components/DemoVideo";
import { SampleNotice } from "../components/SampleNotice";
import { StatusBadge } from "../components/StatusBadge";

export function DemoPage() {
  const qc = useQueryClient();
  const demo = useQuery({ queryKey: ["demo"], queryFn: api.demo.get });
  const reseed = useMutation({
    mutationFn: api.demo.seed,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["demo"] });
      qc.invalidateQueries({ queryKey: ["people"] });
    },
  });

  if (demo.isLoading) return <p className="animate-pulse-soft text-sm text-ivory-300/50">Loading the finished example…</p>;
  if (demo.error) return <p className="text-amber-300">{(demo.error as Error).message}</p>;
  const d = demo.data!;

  return (
    <div className="space-y-8">
      {!d.is_real && <SampleNotice />}

      <div className="panel overflow-hidden">
        <div className="border-b border-champagne-500/30 bg-champagne-500/10 px-6 py-3 text-xs uppercase tracking-[0.2em] text-champagne-400">
          {d.label}
        </div>
        <div className="px-6 py-8">
          <h1 className="font-display text-4xl text-ivory-50">The finished example</h1>
          <p className="mt-3 max-w-2xl text-sm text-ivory-300/60">
            {d.participant_count} people, already run: every profile page, every date between
            their agents, and a personal ranking for each person. Nothing to type.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link className="btn-primary" to={`/participants/${d.first_participant_id}`}>
              1 · Open a profile page
            </Link>
            <Link className="btn-ghost" to={`/dates/${d.showcase_date_ids[0] ?? ""}`}>
              2 · Watch two agents date
            </Link>
            <Link className="btn-ghost" to={`/rankings/${d.first_participant_id}`}>
              3 · See the rankings
            </Link>
          </div>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["People", d.participant_count],
          ["Dates between agents", d.session_count],
          ["Ranking rows", d.ranking_count],
          ["Dating engine", d.run.config.engine ?? d.run.mode],
        ].map(([label, value]) => (
          <div key={String(label)} className="panel p-5">
            <div className="text-[11px] uppercase tracking-[0.16em] text-ivory-300/45">{label}</div>
            <div className="mt-2 font-display text-3xl text-ivory-50">{value}</div>
          </div>
        ))}
      </div>

      <DemoVideo url={d.video_url} />

      <div className="panel p-6">
        <h2 className="font-display text-2xl text-ivory-50">Everyone's best match</h2>
        <p className="mt-1 text-sm text-ivory-300/50">
          Each person's #1 from their own ranking. Click a name for the profile, or the score for the date.
        </p>
        <ul className="mt-4 grid gap-x-8 gap-y-2 md:grid-cols-2">
          {d.top_matches.map((m) => (
            <li key={m.participant_id} className="flex items-center justify-between gap-3 border-b border-ivory-200/5 py-2 text-sm">
              <span className="min-w-0 truncate">
                <Link className="text-ivory-100 hover:text-champagne-400" to={`/participants/${m.participant_id}`}>
                  {m.participant_name}
                </Link>
                <span className="text-ivory-300/40"> → </span>
                <Link className="text-ivory-100 hover:text-champagne-400" to={`/rankings/${m.participant_id}`}>
                  {m.candidate_name}
                </Link>
              </span>
              <Link className="shrink-0 text-xs text-champagne-400 hover:underline" to={`/dates/${m.date_session_id ?? ""}`}>
                {m.score.toFixed(1)} · date →
              </Link>
            </li>
          ))}
        </ul>
      </div>

      <div>
        <h2 className="font-display text-2xl text-ivory-50">Dates worth watching</h2>
        <div className="mt-4 flex flex-wrap gap-2">
          {d.showcase_date_ids.map((id) => (
            <Link key={id} className="btn-ghost" to={`/dates/${id}`}>
              Date #{id}
            </Link>
          ))}
          <Link className="btn-ghost" to={`/dates?run=${d.run.id}`}>
            All {d.session_count} dates
          </Link>
        </div>
      </div>

      <div className="panel p-6">
        <h2 className="font-display text-2xl text-ivory-50">How this run was made</h2>
        <ul className="mt-4 space-y-2 text-sm text-ivory-200/70">
          {d.notes.map((n) => (
            <li key={n} className="flex gap-2">
              <StatusBadge label="Note" tone="demo" />
              <span>{n}</span>
            </li>
          ))}
        </ul>
        {!d.is_real && (
          <button className="btn-ghost mt-5" type="button" onClick={() => reseed.mutate()} disabled={reseed.isPending}>
            {reseed.isPending ? "Rebuilding…" : "Rebuild synthetic sample"}
          </button>
        )}
      </div>
    </div>
  );
}
