import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { RUN_ACTIVE, usePeople, useRun } from "../api/hooks";
import { StatusBadge } from "../components/StatusBadge";
import type { NewParticipant } from "../types";

const LINKEDIN = /linkedin\.com\/in\/[^/\s]+/i;
const INSTAGRAM = /instagram\.com\/[^/\s]+/i;

const schema = z.object({
  display_name: z.string().max(200).optional(),
  linkedin_url: z.string().regex(LINKEDIN, "Paste a linkedin.com/in/… profile link"),
  instagram_url: z.string().regex(INSTAGRAM, "Paste an instagram.com/… profile link"),
  linkedin_text: z.string().max(20000).optional(),
  instagram_text: z.string().max(20000).optional(),
  confirmed: z.literal(true, {
    errorMap: () => ({ message: "Please confirm before reading the profiles" }),
  }),
});

type FormValues = z.infer<typeof schema>;

type BulkRow = {
  line: string;
  status: "queued" | "reading" | "done" | "failed";
  id?: number;
  name?: string;
  error?: string;
};

function toPayload(v: {
  display_name?: string;
  linkedin_url: string;
  instagram_url: string;
  linkedin_text?: string;
  instagram_text?: string;
}): NewParticipant {
  return {
    display_name: v.display_name?.trim() ?? "",
    linkedin_url: v.linkedin_url.trim(),
    instagram_url: v.instagram_url.trim(),
    linkedin_text: v.linkedin_text ?? "",
    instagram_text: v.instagram_text ?? "",
    adult_eligibility_confirmed: true,
    consent_to_agent_dating: true,
  };
}

/** Pulls the two links out of one pasted line, in either order. */
function parseLine(line: string): { linkedin_url: string; instagram_url: string } | null {
  const linkedin = line.match(/\S*linkedin\.com\/in\/[^\s,;]+/i)?.[0];
  const instagram = line.match(/\S*instagram\.com\/[^\s,;]+/i)?.[0];
  return linkedin && instagram ? { linkedin_url: linkedin, instagram_url: instagram } : null;
}

export function WorkspacePage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const people = usePeople();
  const realPeople = people.data && !people.data.isSample ? people.data.items : [];
  const ready = realPeople.filter((p) => p.has_analysis).length;

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { display_name: "", linkedin_url: "", instagram_url: "", linkedin_text: "", instagram_text: "" },
  });

  const create = useMutation({
    mutationFn: (values: FormValues) => api.participants.create(toPayload(values)),
    onSuccess: (person) => {
      qc.invalidateQueries({ queryKey: ["people"] });
      // Profile page first: go straight to what the agent found.
      navigate(`/participants/${person.id}`);
    },
  });

  // ---- bulk add: one person per line, read one after another
  const [bulkText, setBulkText] = useState("");
  const [bulkConfirmed, setBulkConfirmed] = useState(false);
  const [bulkRows, setBulkRows] = useState<BulkRow[]>([]);
  const [bulkBusy, setBulkBusy] = useState(false);

  async function runBulk() {
    const lines = bulkText.split("\n").map((l) => l.trim()).filter((l) => l && !l.startsWith("#"));
    const rows: BulkRow[] = lines.map((line) => ({ line, status: "queued" }));
    setBulkRows(rows);
    setBulkBusy(true);
    for (let i = 0; i < rows.length; i++) {
      const links = parseLine(rows[i].line);
      if (!links) {
        rows[i] = { ...rows[i], status: "failed", error: "Needs one LinkedIn and one Instagram link" };
        setBulkRows([...rows]);
        continue;
      }
      rows[i] = { ...rows[i], status: "reading" };
      setBulkRows([...rows]);
      try {
        const person = await api.participants.create(toPayload(links));
        rows[i] = { ...rows[i], status: "done", id: person.id, name: person.display_name };
      } catch (err) {
        rows[i] = { ...rows[i], status: "failed", error: (err as Error).message };
      }
      setBulkRows([...rows]);
      qc.invalidateQueries({ queryKey: ["people"] });
    }
    setBulkBusy(false);
  }

  // ---- dating run
  const runs = useQuery({ queryKey: ["runs"], queryFn: api.runs.list });
  const [startedRunId, setStartedRunId] = useState<number>();
  const latestLive = runs.data?.find((r) => r.mode === "live");
  const run = useRun(startedRunId ?? latestLive?.id);
  const active = !!run.data && RUN_ACTIVE.has(run.data.status);

  const startRun = useMutation({
    mutationFn: async () => {
      const created = await api.runs.create({
        name: `Everyone dates everyone — ${new Date().toLocaleString()}`,
        mode: "live",
        max_turns: settings.data?.default_max_turns ?? 6,
      });
      return api.runs.start(created.id);
    },
    onSuccess: (started) => {
      setStartedRunId(started.id);
      qc.invalidateQueries({ queryKey: ["runs"] });
      qc.invalidateQueries({ queryKey: ["demo"] });
    },
  });

  const llm = settings.data?.llm_configured;

  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-4xl text-ivory-50">Add people</h1>
          <p className="mt-2 max-w-2xl text-sm text-ivory-300/55">
            Paste two public links per person. Their agent reads both profiles, builds the
            profile page, and is then ready to date everyone else.
          </p>
        </div>
        <StatusBadge
          label={llm ? `Agents: ${settings.data?.llm_model}` : "Agents: rule-based (no LLM key)"}
          tone={llm ? "good" : "demo"}
        />
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        <form className="panel space-y-4 p-6" onSubmit={form.handleSubmit((v) => create.mutate(v))}>
          <div>
            <h2 className="font-display text-2xl text-ivory-50">One person</h2>
            <p className="mt-1 text-xs text-ivory-300/45">
              Exactly two sources: their LinkedIn and their public Instagram. Nothing else is used.
            </p>
          </div>
          <div>
            <label className="label" htmlFor="linkedin_url">LinkedIn link</label>
            <input id="linkedin_url" className="field" placeholder="https://www.linkedin.com/in/username" {...form.register("linkedin_url")} />
            {form.formState.errors.linkedin_url && (
              <p className="mt-1 text-xs text-amber-300">{form.formState.errors.linkedin_url.message}</p>
            )}
          </div>
          <div>
            <label className="label" htmlFor="instagram_url">Instagram link (public profile)</label>
            <input id="instagram_url" className="field" placeholder="https://www.instagram.com/username" {...form.register("instagram_url")} />
            {form.formState.errors.instagram_url && (
              <p className="mt-1 text-xs text-amber-300">{form.formState.errors.instagram_url.message}</p>
            )}
          </div>
          <details className="text-sm text-ivory-300/55">
            <summary className="cursor-pointer text-xs uppercase tracking-[0.14em] text-ivory-300/45">
              Optional — name, or profile text if a site blocks the read
            </summary>
            <div className="mt-3 space-y-3">
              <div>
                <label className="label" htmlFor="display_name">Display name (read from the profiles if blank)</label>
                <input id="display_name" className="field" {...form.register("display_name")} />
              </div>
              <div>
                <label className="label" htmlFor="linkedin_text">LinkedIn profile text (fallback only)</label>
                <textarea id="linkedin_text" className="field min-h-[70px]" {...form.register("linkedin_text")} />
              </div>
              <div>
                <label className="label" htmlFor="instagram_text">Instagram bio + captions (fallback only)</label>
                <textarea id="instagram_text" className="field min-h-[70px]" {...form.register("instagram_text")} />
              </div>
            </div>
          </details>
          <label className="flex items-start gap-2 text-sm text-ivory-200/70">
            <input type="checkbox" className="mt-1" {...form.register("confirmed")} />
            Both profiles are public, belong to the same adult, and I may use them here.
          </label>
          {form.formState.errors.confirmed && (
            <p className="text-xs text-amber-300">{form.formState.errors.confirmed.message}</p>
          )}
          {create.error && <p className="text-sm text-amber-300">{(create.error as Error).message}</p>}
          <button className="btn-primary" type="submit" disabled={create.isPending}>
            {create.isPending ? "Reading LinkedIn + Instagram, then analyzing…" : "Read profiles & build profile page"}
          </button>
          {create.isPending && (
            <p className="animate-pulse-soft text-xs text-champagne-400">
              The agent is reading both public profiles. This usually takes 5–20 seconds.
            </p>
          )}
        </form>

        <div className="panel space-y-4 p-6">
          <div>
            <h2 className="font-display text-2xl text-ivory-50">Many people at once</h2>
            <p className="mt-1 text-xs text-ivory-300/45">
              One person per line: a LinkedIn link and an Instagram link, separated by a comma or space.
            </p>
          </div>
          <textarea
            className="field min-h-[150px] font-mono text-xs"
            placeholder={"https://www.linkedin.com/in/person-one, https://www.instagram.com/personone\nhttps://www.linkedin.com/in/person-two, https://www.instagram.com/persontwo"}
            value={bulkText}
            onChange={(e) => setBulkText(e.target.value)}
            aria-label="Bulk links"
          />
          <label className="flex items-start gap-2 text-sm text-ivory-200/70">
            <input type="checkbox" className="mt-1" checked={bulkConfirmed} onChange={(e) => setBulkConfirmed(e.target.checked)} />
            All of these are public profiles of adults that I may use here.
          </label>
          <button
            className="btn-primary"
            type="button"
            disabled={bulkBusy || !bulkConfirmed || !bulkText.trim()}
            onClick={runBulk}
          >
            {bulkBusy ? "Reading profiles…" : "Read everyone"}
          </button>
          {bulkRows.length > 0 && (
            <ul className="max-h-64 space-y-2 overflow-auto text-xs">
              {bulkRows.map((row, i) => (
                <li key={i} className="flex items-start justify-between gap-3 border-b border-ivory-200/5 pb-2">
                  <span className="min-w-0 flex-1 break-all text-ivory-300/60">
                    {row.status === "done" && row.id ? (
                      <Link className="text-champagne-400 hover:underline" to={`/participants/${row.id}`}>
                        {row.name} — open profile
                      </Link>
                    ) : (
                      row.line
                    )}
                    {row.error && <span className="mt-1 block text-amber-300">{row.error}</span>}
                  </span>
                  <StatusBadge
                    label={row.status}
                    tone={row.status === "done" ? "good" : row.status === "failed" ? "warn" : row.status === "reading" ? "demo" : "neutral"}
                  />
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        <div className="panel p-6">
          <div className="flex items-baseline justify-between">
            <h2 className="font-display text-2xl text-ivory-50">People so far</h2>
            <span className="text-sm text-ivory-300/50">{realPeople.length} added · {ready} analyzed</span>
          </div>
          <ul className="mt-4 max-h-80 space-y-2 overflow-auto">
            {realPeople.map((p) => (
              <li key={p.id} className="flex items-center justify-between gap-3 border-b border-ivory-200/5 py-2 text-sm">
                <Link to={`/participants/${p.id}`} className="min-w-0 flex-1">
                  <span className="text-ivory-100 hover:text-champagne-400">{p.display_name}</span>
                  {p.headline && <span className="block truncate text-xs text-ivory-300/40">{p.headline}</span>}
                </Link>
                <StatusBadge label={p.has_analysis ? "analyzed" : "not analyzed"} tone={p.has_analysis ? "good" : "warn"} />
              </li>
            ))}
            {!realPeople.length && (
              <li className="text-sm text-ivory-300/40">Nobody yet — paste a pair of links above.</li>
            )}
          </ul>
        </div>

        <div className="panel p-6">
          <h2 className="font-display text-2xl text-ivory-50">Let the agents date</h2>
          <p className="mt-2 text-sm text-ivory-300/50">
            Every agent goes on a one-to-one date with every other agent
            {ready >= 2 && ` — ${(ready * (ready - 1)) / 2} dates for ${ready} people`}. Each agent then
            files its own verdict, and every person gets a personal ranking.
          </p>
          <button
            className="btn-primary mt-4"
            type="button"
            disabled={startRun.isPending || active || ready < 2}
            onClick={() => startRun.mutate()}
          >
            {active ? "Agents are dating…" : startRun.isPending ? "Starting…" : "Start dating"}
          </button>
          {ready < 2 && <p className="mt-2 text-xs text-ivory-300/40">Add at least two people first.</p>}
          {startRun.error && <p className="mt-2 text-sm text-amber-300">{(startRun.error as Error).message}</p>}

          {run.data && run.data.mode === "live" && (
            <div className="mt-5 space-y-2 border-t border-ivory-200/10 pt-4 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-ivory-200/80">Run #{run.data.id}</span>
                <div className="flex gap-2">
                  <StatusBadge label={String(run.data.config.engine ?? "")} tone="demo" />
                  <StatusBadge
                    label={run.data.status.replace(/_/g, " ")}
                    tone={run.data.status.startsWith("completed") ? "good" : active ? "demo" : "warn"}
                  />
                </div>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-ink-700" role="progressbar" aria-valuenow={run.data.progress} aria-valuemin={0} aria-valuemax={100}>
                <div className="h-full rounded-full bg-champagne-500 transition-all duration-500" style={{ width: `${run.data.progress}%` }} />
              </div>
              <p className="text-xs text-ivory-300/50">
                {run.data.completed_sessions} of {run.data.session_count} dates finished · {run.data.participant_count} people
              </p>
              {run.data.error_summary && <p className="text-xs text-amber-300">{run.data.error_summary}</p>}
              <div className="flex flex-wrap gap-2 pt-2">
                <Link className="btn-ghost" to={`/dates?run=${run.data.id}`}>
                  {active ? "Watch dates live" : "Watch the dates"}
                </Link>
                {run.data.status.startsWith("completed") && (
                  <Link className="btn-ghost" to="/rankings">See rankings</Link>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
