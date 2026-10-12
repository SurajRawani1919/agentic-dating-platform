import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { ConfidenceBar } from "../components/ConfidenceBar";
import { EvidenceList } from "../components/EvidenceList";
import { StatusBadge } from "../components/StatusBadge";
import type { SourceRecord } from "../types";

const SOURCE_LABEL = { linkedin: "LinkedIn", instagram: "Instagram" } as const;

function SourceCard({ source }: { source: SourceRecord }) {
  const read = source.acquisition_status === "acquired";
  const usable = read || source.acquisition_status === "participant_provided";
  return (
    <div className="panel p-5">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm uppercase tracking-[0.16em] text-ivory-300/60">
          {SOURCE_LABEL[source.source_type]}
        </h3>
        <StatusBadge
          label={read ? "read from link" : source.acquisition_status.replace(/_/g, " ")}
          tone={read ? "good" : usable ? "demo" : "warn"}
        />
      </div>
      <a
        className="mt-2 block truncate text-sm text-champagne-400 hover:underline"
        href={source.submitted_url}
        target="_blank"
        rel="noreferrer"
      >
        {source.submitted_url} →
      </a>
      <p className="mt-2 text-xs text-ivory-300/45">{source.verification_notes}</p>
      {source.content ? (
        <details className="mt-3 border-t border-ivory-200/10 pt-3">
          <summary className="cursor-pointer text-xs uppercase tracking-[0.14em] text-champagne-500/80">
            What the agent read ({source.content.length.toLocaleString()} characters)
          </summary>
          <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-sm bg-ink-950/60 p-3 font-sans text-xs leading-relaxed text-ivory-300/70">
            {source.content}
          </pre>
        </details>
      ) : (
        <p className="mt-3 border-t border-ivory-200/10 pt-3 text-xs text-amber-200/70">
          Nothing could be read from this profile.
        </p>
      )}
    </div>
  );
}

export function ParticipantDetailPage() {
  const { id } = useParams();
  const pid = Number(id);
  const qc = useQueryClient();
  const navigate = useNavigate();

  const participant = useQuery({
    queryKey: ["participant", pid],
    queryFn: () => api.participants.get(pid),
    enabled: Number.isFinite(pid),
  });

  const analysis = useQuery({
    queryKey: ["analysis", pid],
    queryFn: () => api.participants.analysis(pid),
    enabled: Number.isFinite(pid),
    retry: false,
  });

  const refreshed = () => {
    qc.invalidateQueries({ queryKey: ["analysis", pid] });
    qc.invalidateQueries({ queryKey: ["participant", pid] });
    qc.invalidateQueries({ queryKey: ["people"] });
  };
  const reread = useMutation({ mutationFn: () => api.participants.refresh(pid), onSuccess: refreshed });
  const analyze = useMutation({ mutationFn: () => api.participants.analyze(pid), onSuccess: refreshed });
  const remove = useMutation({
    mutationFn: () => api.participants.remove(pid),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["people"] });
      qc.invalidateQueries({ queryKey: ["demo"] });
      navigate("/participants");
    },
  });

  if (participant.isLoading) return <p className="text-sm text-ivory-300/50">Loading profile…</p>;
  if (participant.error || !participant.data)
    return <p className="text-amber-300">{(participant.error as Error)?.message ?? "Not found"}</p>;

  const p = participant.data;
  const a = analysis.data;
  const ruleBased = !!a && (a.model_name.includes("deterministic") || a.model_name.includes("rule"));
  const busy = reread.isPending || analyze.isPending;
  const error = (reread.error ?? analyze.error ?? remove.error) as Error | null;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-[0.2em] text-champagne-500/80">Profile page</p>
          <h1 className="mt-2 font-display text-4xl text-ivory-50">{p.display_name}</h1>
          {a?.headline && <p className="mt-2 max-w-2xl text-lg text-ivory-200/75">{a.headline}</p>}
          <div className="mt-3 flex flex-wrap gap-2">
            {p.is_synthetic && <StatusBadge label="Synthetic sample — not a real person" tone="warn" />}
            <StatusBadge
              label={
                p.source_verification_status === "plausibly_matched"
                  ? "Both links match one person"
                  : `Identity: ${p.source_verification_status.replace(/_/g, " ")}`
              }
              tone={p.source_verification_status === "plausibly_matched" ? "good" : "neutral"}
            />
            {a && (
              <StatusBadge
                label={ruleBased ? "Analyzed by rule-based agent" : `Analyzed by ${a.model_name}`}
                tone={ruleBased ? "demo" : "good"}
              />
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link className="btn-primary" to={`/rankings/${p.id}`}>
            Who fits them best
          </Link>
          {!p.is_synthetic && (
            <button className="btn-ghost" onClick={() => reread.mutate()} disabled={busy}>
              {reread.isPending ? "Re-reading…" : "Re-read both profiles"}
            </button>
          )}
          {!p.is_synthetic && (
            <button
              className="btn-ghost"
              onClick={() => {
                if (window.confirm(`Remove ${p.display_name} and all of their data?`)) remove.mutate();
              }}
              disabled={remove.isPending}
            >
              Remove
            </button>
          )}
        </div>
      </div>

      {error && <p className="text-sm text-amber-300">{error.message}</p>}

      <section>
        <h2 className="mb-3 text-xs uppercase tracking-[0.18em] text-ivory-300/55">
          The two sources — nothing else is used
        </h2>
        <div className="grid gap-4 md:grid-cols-2">
          {p.sources.map((s) => (
            <SourceCard key={s.id} source={s} />
          ))}
        </div>
      </section>

      {!a && !analysis.isFetching && (
        <div className="panel flex flex-wrap items-center justify-between gap-4 p-6 text-sm text-ivory-300/60">
          <span>This person has not been analyzed yet.</span>
          <button className="btn-primary" onClick={() => analyze.mutate()} disabled={busy}>
            {analyze.isPending ? "Analyzing…" : "Analyze now"}
          </button>
        </div>
      )}

      {a && (
        <div className="space-y-6">
          <div className="panel p-6">
            <h2 className="font-display text-2xl text-ivory-50">Who they are</h2>
            <p className="mt-3 text-base leading-relaxed text-ivory-100/85">{a.summary}</p>
            {a.ideal_date && (
              <p className="mt-4 border-l-2 border-champagne-500/50 pl-4 text-sm text-ivory-200/75">
                <span className="block text-[11px] uppercase tracking-[0.16em] text-champagne-500/80">
                  A first date they would enjoy
                </span>
                {a.ideal_date}
              </p>
            )}
            <div className="mt-6 grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
              {Object.entries(a.confidence_by_attribute || {}).map(([k, v]) => (
                <ConfidenceBar key={k} label={k} value={Number(v)} />
              ))}
            </div>
          </div>

          <EvidenceList
            title="Needs"
            subtitle="What this person needs from a partner — inferred by their agent, each with the evidence behind it."
            items={a.needs}
            emphasis
            empty="The profiles do not give enough to infer needs."
          />

          <div className="grid gap-4 md:grid-cols-2">
            <EvidenceList title="Hobbies" subtitle="What they do for fun." items={a.hobbies} emphasis />
            <EvidenceList title="Interests" subtitle="What they think and post about." items={a.interests} emphasis />
          </div>

          <div>
            <h2 className="mb-3 text-xs uppercase tracking-[0.18em] text-ivory-300/55">Other qualities</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <EvidenceList title="Values" items={a.core_values} />
              <EvidenceList title="Personality" items={a.personality_traits} />
              <EvidenceList title="Lifestyle" items={a.lifestyle_clues} />
              <EvidenceList title="How they communicate" items={a.communication_clues} />
              {a.explicitly_stated_preferences.length > 0 && (
                <EvidenceList title="Stated in their own words" items={a.explicitly_stated_preferences} />
              )}
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="panel p-5">
              <h3 className="text-sm uppercase tracking-[0.16em] text-ivory-300/55">
                What the agent does not know
              </h3>
              <ul className="mt-3 space-y-2 text-sm text-ivory-200/70">
                {(a.missing_information || []).map((x) => (
                  <li key={x}>• {x}</li>
                ))}
                {(a.uncertainty_notes || []).map((x) => (
                  <li key={x} className="text-ivory-300/45">• {x}</li>
                ))}
              </ul>
            </div>
            {(a.contradictions || []).length > 0 && (
              <div className="panel p-5">
                <h3 className="text-sm uppercase tracking-[0.16em] text-ivory-300/55">Contradictions</h3>
                <ul className="mt-3 space-y-2 text-sm text-ivory-200/70">
                  {a.contradictions.map((x) => (
                    <li key={x}>• {x}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <Link className="btn-primary" to={`/rankings/${p.id}`}>
              See {p.display_name.split(" ")[0]}'s ranking
            </Link>
            <button className="btn-ghost" onClick={() => analyze.mutate()} disabled={busy}>
              {analyze.isPending ? "Analyzing…" : "Re-run analysis"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
