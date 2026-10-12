import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { ConfidenceBar } from "../components/ConfidenceBar";
import { StatusBadge } from "../components/StatusBadge";

export function RankingDetailPage() {
  const { participantId } = useParams();
  const pid = Number(participantId);
  const [sort, setSort] = useState<"rank" | "score" | "confidence">("rank");
  const [q, setQ] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["rankings", pid],
    queryFn: () => api.rankings.forParticipant(pid),
    enabled: Number.isFinite(pid),
  });

  const rows = useMemo(() => {
    let list = [...(data?.rankings ?? [])];
    if (q.trim()) {
      const needle = q.toLowerCase();
      list = list.filter((r) => (r.candidate_name || "").toLowerCase().includes(needle));
    }
    if (sort === "score") list.sort((a, b) => b.compatibility_score - a.compatibility_score);
    if (sort === "confidence") list.sort((a, b) => b.confidence - a.confidence);
    if (sort === "rank") list.sort((a, b) => a.rank - b.rank);
    return list;
  }, [data, sort, q]);

  if (isLoading) return <p className="text-sm text-ivory-300/50">Loading rankings…</p>;
  if (error || !data)
    return <p className="text-amber-300">{(error as Error)?.message ?? "Not found"}</p>;

  return (
    <div className="space-y-8">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-champagne-500/80">
          Rankings · run #{data.run_id}
        </p>
        <h1 className="mt-2 font-display text-4xl text-ivory-50">{data.participant_name}</h1>
        <p className="mt-2 text-sm text-ivory-300/55">
          {data.rankings.length} candidates · scores from persisted date evaluations
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        <input
          className="field max-w-xs"
          placeholder="Filter candidates"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select
          className="field max-w-[180px]"
          value={sort}
          onChange={(e) => setSort(e.target.value as typeof sort)}
        >
          <option value="rank">Sort by rank</option>
          <option value="score">Sort by score</option>
          <option value="confidence">Sort by confidence</option>
        </select>
        <Link className="btn-ghost" to={`/participants/${pid}`}>
          Profile
        </Link>
      </div>

      <div className="space-y-3">
        {rows.map((r) => (
          <article key={r.id} className="panel p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.16em] text-champagne-500/80">
                  Rank {r.rank}
                </div>
                <h2 className="mt-1 font-display text-2xl text-ivory-50">
                  <Link className="hover:text-champagne-400" to={`/participants/${r.candidate_id}`}>
                    {r.candidate_name}
                  </Link>
                </h2>
                <div className="mt-2 flex flex-wrap gap-2">
                  {r.candidate_is_synthetic && <StatusBadge label="Synthetic" tone="demo" />}
                  <StatusBadge label={`Score ${r.compatibility_score}`} />
                </div>
              </div>
              <div className="w-40">
                <ConfidenceBar label="Confidence" value={r.confidence} />
              </div>
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-3">
              <div>
                <h3 className="text-[11px] uppercase tracking-[0.14em] text-ivory-300/45">Why it may work</h3>
                <ul className="mt-2 space-y-1 text-sm text-ivory-200/70">
                  {(r.positive_evidence || []).slice(0, 5).map((x) => (
                    <li key={x}>• {x}</li>
                  ))}
                  {!r.positive_evidence?.length && <li className="text-ivory-300/35">Thin evidence</li>}
                </ul>
              </div>
              <div>
                <h3 className="text-[11px] uppercase tracking-[0.14em] text-ivory-300/45">Potential friction</h3>
                <ul className="mt-2 space-y-1 text-sm text-ivory-200/70">
                  {(r.potential_mismatches || []).slice(0, 5).map((x) => (
                    <li key={x}>• {x}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h3 className="text-[11px] uppercase tracking-[0.14em] text-ivory-300/45">Still unknown</h3>
                <ul className="mt-2 space-y-1 text-sm text-ivory-200/70">
                  {(r.unanswered_questions || []).slice(0, 5).map((x) => (
                    <li key={x}>• {x}</li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {r.date_session_id && (
                <Link className="btn-ghost" to={`/dates/${r.date_session_id}`}>
                  Open date transcript
                </Link>
              )}
              <details className="w-full">
                <summary className="cursor-pointer text-xs uppercase tracking-[0.14em] text-champagne-500/80">
                  Component scores
                </summary>
                <pre className="mt-2 overflow-auto rounded-sm bg-ink-950/60 p-3 text-xs text-ivory-300/60">
                  {JSON.stringify(r.score_breakdown, null, 2)}
                </pre>
              </details>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
