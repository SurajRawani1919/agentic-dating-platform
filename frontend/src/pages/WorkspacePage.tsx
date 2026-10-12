import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";

const schema = z.object({
  display_name: z.string().min(1, "Name required"),
  linkedin_url: z.string().url(),
  instagram_url: z.string().url(),
  linkedin_text: z.string().max(20000).optional(),
  instagram_text: z.string().max(20000).optional(),
  adult_eligibility_confirmed: z.literal(true, {
    errorMap: () => ({ message: "Adult confirmation required" }),
  }),
  consent_to_agent_dating: z.literal(true, {
    errorMap: () => ({ message: "Consent required" }),
  }),
});

type FormValues = z.infer<typeof schema>;

export function WorkspacePage() {
  const qc = useQueryClient();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const participants = useQuery({
    queryKey: ["participants"],
    queryFn: () => api.participants.list(),
  });

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      display_name: "",
      linkedin_url: "",
      instagram_url: "",
      linkedin_text: "",
      instagram_text: "",
    },
  });

  const create = useMutation({
    mutationFn: (values: FormValues) => api.participants.create(values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["participants"] });
      form.reset();
    },
  });

  const startRun = useMutation({
    mutationFn: async () => {
      const run = await api.runs.create({
        name: "Live cohort run",
        mode: health.data?.llm_configured ? "live" : "demo",
        max_turns: 6,
      });
      if (health.data?.llm_configured) {
        return api.runs.start(run.id);
      }
      return run;
    },
  });

  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-4xl text-ivory-50">Workspace</h1>
          <p className="mt-2 text-sm text-ivory-300/55">
            Add consenting participants, analyze profiles, then run agent dating.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge
            label={health.data?.llm_configured ? "LLM ready" : "Demo / deterministic"}
            tone={health.data?.llm_configured ? "good" : "demo"}
          />
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        <form
          className="panel space-y-4 p-6"
          onSubmit={form.handleSubmit((v) => create.mutate(v))}
        >
          <h2 className="font-display text-2xl text-ivory-50">Add participant</h2>
          <div>
            <label className="label">Display name</label>
            <input className="field" {...form.register("display_name")} />
            {form.formState.errors.display_name && (
              <p className="mt-1 text-xs text-amber-300">{form.formState.errors.display_name.message}</p>
            )}
          </div>
          <div>
            <label className="label">LinkedIn URL</label>
            <input className="field" placeholder="https://www.linkedin.com/in/..." {...form.register("linkedin_url")} />
          </div>
          <div>
            <label className="label">Instagram URL</label>
            <input className="field" placeholder="https://www.instagram.com/..." {...form.register("instagram_url")} />
          </div>
          <div>
            <label className="label">Authorized LinkedIn text (required when scraping unavailable)</label>
            <textarea className="field min-h-[90px]" {...form.register("linkedin_text")} />
          </div>
          <div>
            <label className="label">Authorized Instagram text</label>
            <textarea className="field min-h-[90px]" {...form.register("instagram_text")} />
          </div>
          <label className="flex items-start gap-2 text-sm text-ivory-200/70">
            <input type="checkbox" className="mt-1" {...form.register("adult_eligibility_confirmed")} />
            I confirm this participant is 18+ and eligible.
          </label>
          <label className="flex items-start gap-2 text-sm text-ivory-200/70">
            <input type="checkbox" className="mt-1" {...form.register("consent_to_agent_dating")} />
            Participant consents to AI agent dating using only permitted LinkedIn + Instagram content.
          </label>
          {create.error && (
            <p className="text-sm text-amber-300">{(create.error as Error).message}</p>
          )}
          {create.isSuccess && (
            <p className="text-sm text-emerald-300/80">Participant saved. Continue to analysis.</p>
          )}
          <button className="btn-primary" type="submit" disabled={create.isPending}>
            {create.isPending ? "Saving…" : "Save participant"}
          </button>
        </form>

        <div className="space-y-4">
          <div className="panel p-6">
            <h2 className="font-display text-2xl text-ivory-50">Cohort</h2>
            <p className="mt-1 text-sm text-ivory-300/50">
              {participants.data?.total ?? 0} participants
            </p>
            <ul className="mt-4 max-h-72 space-y-2 overflow-auto">
              {(participants.data?.items ?? []).map((p) => (
                <li key={p.id} className="flex items-center justify-between border-b border-ivory-200/5 py-2 text-sm">
                  <Link to={`/participants/${p.id}`} className="text-ivory-100 hover:text-champagne-400">
                    {p.display_name}
                  </Link>
                  <div className="flex gap-2">
                    {p.is_synthetic && <StatusBadge label="Synthetic" tone="demo" />}
                    <StatusBadge label={p.source_verification_status} />
                  </div>
                </li>
              ))}
              {!participants.data?.items.length && (
                <li className="text-sm text-ivory-300/40">No participants yet — add one or open the demo.</li>
              )}
            </ul>
          </div>
          <div className="panel p-6">
            <h2 className="font-display text-xl text-ivory-50">Run dating</h2>
            <p className="mt-2 text-sm text-ivory-300/50">
              Creates unique pairs, runs bounded multi-turn sessions in the background, then ranks.
            </p>
            <button
              className="btn-primary mt-4"
              type="button"
              disabled={startRun.isPending || (participants.data?.total ?? 0) < 2}
              onClick={() => startRun.mutate()}
            >
              {startRun.isPending ? "Starting…" : "Create dating run"}
            </button>
            {startRun.data && (
              <p className="mt-3 text-sm text-ivory-200/70">
                Run #{startRun.data.id} — {startRun.data.status}.{" "}
                <Link className="text-champagne-400" to="/dates">
                  View dates
                </Link>
              </p>
            )}
            {startRun.error && (
              <p className="mt-2 text-sm text-amber-300">{(startRun.error as Error).message}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
