import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";

export function DatesPage() {
  const demo = useQuery({ queryKey: ["demo"], queryFn: api.demo.get });
  const sessions = useQuery({
    queryKey: ["sessions", demo.data?.run.id],
    queryFn: () => api.runs.sessions(demo.data!.run.id),
    enabled: !!demo.data?.run.id,
  });

  const showcase = (sessions.data ?? []).filter((s) =>
    demo.data?.showcase_date_ids.includes(s.id),
  );
  const list = showcase.length ? showcase : (sessions.data ?? []).slice(0, 12);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-4xl text-ivory-50">Dating sessions</h1>
        <p className="mt-2 text-sm text-ivory-300/55">
          Multi-turn agent conversations with persisted transcripts and evaluations.
        </p>
      </div>
      {demo.data && (
        <div className="panel flex flex-wrap items-center justify-between gap-3 p-4 text-sm">
          <span>
            Run #{demo.data.run.id} · {demo.data.run.completed_sessions}/{demo.data.run.session_count} completed
          </span>
          <StatusBadge label={demo.data.run.mode} tone="demo" />
        </div>
      )}
      <div className="space-y-3">
        {list.map((s) => (
          <Link
            key={s.id}
            to={`/dates/${s.id}`}
            className="panel flex flex-wrap items-center justify-between gap-3 p-5 transition hover:border-champagne-500/30"
          >
            <div>
              <h2 className="font-display text-xl text-ivory-50">
                {s.participant_a_name} × {s.participant_b_name}
              </h2>
              <p className="mt-1 text-xs text-ivory-300/45">
                Turns {s.current_turn}/{s.max_turns}
                {s.compatibility_score != null && ` · Score ${s.compatibility_score}`}
              </p>
            </div>
            <div className="flex gap-2">
              {s.is_demo_replay && <StatusBadge label="Demo replay" tone="demo" />}
              <StatusBadge label={s.status} tone={s.status === "completed" ? "good" : "neutral"} />
            </div>
          </Link>
        ))}
      </div>
      {!list.length && !sessions.isLoading && (
        <p className="text-sm text-ivory-300/40">
          No sessions yet. <Link className="text-champagne-400" to="/demo">Open demo</Link>.
        </p>
      )}
    </div>
  );
}
