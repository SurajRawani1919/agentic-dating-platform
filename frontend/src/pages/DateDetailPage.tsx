import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { ConfidenceBar } from "../components/ConfidenceBar";
import { StatusBadge } from "../components/StatusBadge";

export function DateDetailPage() {
  const { id } = useParams();
  const dateId = Number(id);
  const { data, isLoading, error } = useQuery({
    queryKey: ["transcript", dateId],
    queryFn: () => api.dates.transcript(dateId),
    enabled: Number.isFinite(dateId),
    refetchInterval: (q) =>
      q.state.data?.session.status === "in_progress" ? 2000 : false,
  });

  if (isLoading) return <p className="animate-pulse-soft text-sm text-ivory-300/50">Loading date room…</p>;
  if (error || !data) return <p className="text-amber-300">{(error as Error)?.message ?? "Not found"}</p>;

  const { session, messages } = data;
  const breakdown = session.score_breakdown || {};

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-champagne-500/80">Dating room</p>
          <h1 className="mt-2 font-display text-4xl text-ivory-50">
            {session.participant_a_name} × {session.participant_b_name}
          </h1>
          <div className="mt-3 flex flex-wrap gap-2">
            <StatusBadge label={session.status} tone={session.status === "completed" ? "good" : "warn"} />
            {session.is_demo_replay ? (
              <StatusBadge label="Saved demo replay — not a live LLM stream" tone="demo" />
            ) : (
              <StatusBadge label="Live / persisted session" tone="good" />
            )}
          </div>
        </div>
        <div className="text-right text-sm text-ivory-300/55">
          <div>Turn {session.current_turn} / {session.max_turns}</div>
          {session.compatibility_score != null && (
            <div className="mt-1 text-champagne-400">Score {session.compatibility_score}</div>
          )}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        <div className="panel p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm uppercase tracking-[0.16em] text-ivory-300/55">Transcript</h2>
            {session.status === "in_progress" && (
              <span className="animate-pulse-soft text-xs text-champagne-400">Agents typing…</span>
            )}
          </div>
          <ol className="space-y-4">
            {messages.map((m) => {
              const left = m.speaker_participant_id === session.participant_a_id;
              return (
                <li
                  key={m.id}
                  className={`max-w-[90%] rounded-sm border border-ivory-200/10 p-4 ${
                    left ? "mr-auto bg-ink-800/60" : "ml-auto bg-ink-700/40"
                  }`}
                >
                  <div className="mb-2 flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-[0.14em] text-ivory-300/45">
                    <span>{left ? session.participant_a_name : session.participant_b_name}</span>
                    <StatusBadge label={m.intent} />
                    <StatusBadge
                      label={m.is_live_llm ? `Live · ${m.model_name}` : `Replay · ${m.model_name}`}
                      tone={m.is_live_llm ? "good" : "demo"}
                    />
                  </div>
                  <p className="text-sm leading-relaxed text-ivory-100/90">{m.message}</p>
                  {m.question && (
                    <p className="mt-2 text-sm text-champagne-400/90">Q: {m.question}</p>
                  )}
                </li>
              );
            })}
            {!messages.length && (
              <li className="text-sm text-ivory-300/40">No messages persisted yet.</li>
            )}
          </ol>
        </div>

        <aside className="space-y-4">
          <div className="panel p-4">
            <h3 className="text-xs uppercase tracking-[0.16em] text-ivory-300/55">Shared interests</h3>
            <ul className="mt-2 space-y-1 text-sm text-ivory-200/75">
              {(session.shared_interests || []).slice(0, 8).map((x) => (
                <li key={x}>• {x}</li>
              ))}
              {!session.shared_interests?.length && (
                <li className="text-ivory-300/35">None confirmed</li>
              )}
            </ul>
          </div>
          <div className="panel p-4">
            <h3 className="text-xs uppercase tracking-[0.16em] text-ivory-300/55">Friction</h3>
            <ul className="mt-2 space-y-1 text-sm text-ivory-200/75">
              {(session.potential_friction || []).map((x) => (
                <li key={x}>• {x}</li>
              ))}
            </ul>
          </div>
          {session.confidence != null && (
            <div className="panel p-4">
              <ConfidenceBar label="Session confidence" value={session.confidence} />
            </div>
          )}
          <div className="panel p-4">
            <h3 className="text-xs uppercase tracking-[0.16em] text-ivory-300/55">Score breakdown</h3>
            <ul className="mt-3 space-y-3">
              {Object.entries(breakdown).map(([k, v]) => {
                const row = v as { score?: number; weight?: number; uncertainty?: number };
                return (
                  <li key={k}>
                    <div className="mb-1 flex justify-between text-[11px] uppercase tracking-[0.12em] text-ivory-300/45">
                      <span>{k.replace(/_/g, " ")}</span>
                      <span>{row.score ?? "—"}</span>
                    </div>
                    <ConfidenceBar value={(row.score ?? 0) / 100} />
                  </li>
                );
              })}
            </ul>
          </div>
          <Link className="btn-ghost w-full" to="/rankings">
            View rankings
          </Link>
        </aside>
      </div>

      {session.date_summary && (
        <div className="panel p-6">
          <h2 className="font-display text-2xl text-ivory-50">Date report</h2>
          <p className="mt-3 text-sm leading-relaxed text-ivory-200/75">{session.date_summary}</p>
        </div>
      )}
    </div>
  );
}
