import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { RUN_ACTIVE, useRun } from "../api/hooks";
import { SampleNotice } from "../components/SampleNotice";
import { StatusBadge } from "../components/StatusBadge";

export function DatesPage() {
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState("");
  const demo = useQuery({ queryKey: ["demo"], queryFn: api.demo.get });
  const runs = useQuery({ queryKey: ["runs"], queryFn: api.runs.list });

  // ?run= wins; otherwise show the saved example (the finished real run when one exists).
  const runId = Number(params.get("run")) || demo.data?.run.id;
  const run = useRun(runId);
  const active = !!run.data && RUN_ACTIVE.has(run.data.status);

  const sessions = useQuery({
    queryKey: ["sessions", runId],
    queryFn: () => api.runs.sessions(runId!),
    enabled: !!runId,
    refetchInterval: active ? 2000 : false,
  });

  const list = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return [...(sessions.data ?? [])]
      .filter(
        (s) =>
          !needle ||
          `${s.participant_a_name} ${s.participant_b_name}`.toLowerCase().includes(needle),
      )
      .sort((a, b) => (b.compatibility_score ?? -1) - (a.compatibility_score ?? -1));
  }, [sessions.data, q]);

  const options = runs.data ?? [];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-4xl text-ivory-50">The agents dating</h1>
        <p className="mt-2 max-w-2xl text-sm text-ivory-300/55">
          Every pair of agents goes on a one-to-one date. Open any date to read — or replay —
          the conversation and each agent's private verdict.
        </p>
      </div>

      {run.data?.mode === "demo" && <SampleNotice />}

      {run.data && (
        <div className="panel space-y-3 p-4 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-ivory-200/80">
              Run #{run.data.id} · {run.data.completed_sessions}/{run.data.session_count} dates
              finished · {run.data.participant_count} people
            </span>
            <div className="flex flex-wrap items-center gap-2">
              {run.data.config.engine && <StatusBadge label={run.data.config.engine} tone="demo" />}
              <StatusBadge
                label={run.data.status.replace(/_/g, " ")}
                tone={run.data.status.startsWith("completed") ? "good" : active ? "demo" : "warn"}
              />
            </div>
          </div>
          {active && (
            <div className="h-1.5 overflow-hidden rounded-full bg-ink-700">
              <div
                className="h-full rounded-full bg-champagne-500 transition-all duration-500"
                style={{ width: `${run.data.progress}%` }}
              />
            </div>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        <input
          className="field max-w-xs"
          placeholder="Find a person"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Find a person"
        />
        {options.length > 1 && (
          <select
            className="field max-w-xs"
            value={runId ?? ""}
            onChange={(e) => setParams({ run: e.target.value })}
            aria-label="Choose a run"
          >
            {options.map((r) => (
              <option key={r.id} value={r.id}>
                Run #{r.id} — {r.participant_count} people{r.mode === "demo" ? " (synthetic sample)" : ""}
              </option>
            ))}
          </select>
        )}
      </div>

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
                {s.current_turn}/{s.max_turns} turns
                {s.compatibility_score != null && ` · mutual score ${s.compatibility_score}`}
              </p>
            </div>
            <StatusBadge
              label={s.status.replace(/_/g, " ")}
              tone={s.status === "completed" ? "good" : s.status === "in_progress" ? "demo" : "neutral"}
            />
          </Link>
        ))}
      </div>
      {!list.length && !sessions.isLoading && (
        <p className="text-sm text-ivory-300/40">
          No dates yet.{" "}
          <Link className="text-champagne-400" to="/app">
            Add people and start dating
          </Link>
          .
        </p>
      )}
    </div>
  );
}
