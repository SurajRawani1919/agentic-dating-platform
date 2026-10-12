import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { ConfidenceBar } from "../components/ConfidenceBar";
import { StatusBadge } from "../components/StatusBadge";

export function ParticipantDetailPage() {
  const { id } = useParams();
  const pid = Number(id);
  const qc = useQueryClient();

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

  const analyze = useMutation({
    mutationFn: () => api.participants.analyze(pid),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["analysis", pid] });
      qc.invalidateQueries({ queryKey: ["participant", pid] });
    },
  });

  const remove = useMutation({
    mutationFn: () => api.participants.remove(pid),
  });

  if (participant.isLoading) return <p className="text-sm text-ivory-300/50">Loading profile…</p>;
  if (participant.error || !participant.data)
    return <p className="text-amber-300">{(participant.error as Error)?.message ?? "Not found"}</p>;

  const p = participant.data;
  const a = analysis.data;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-champagne-500/80">Profile analysis</p>
          <h1 className="mt-2 font-display text-4xl text-ivory-50">{p.display_name}</h1>
          <div className="mt-3 flex flex-wrap gap-2">
            {p.is_synthetic && <StatusBadge label="Synthetic — not a real person" tone="demo" />}
            <StatusBadge label={`Verification: ${p.source_verification_status}`} />
            <StatusBadge label={`Consent: ${p.consent_status}`} tone="good" />
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-primary" onClick={() => analyze.mutate()} disabled={analyze.isPending}>
            {analyze.isPending ? "Analyzing…" : a ? "Reanalyze" : "Analyze"}
          </button>
          <Link className="btn-ghost" to={`/rankings/${p.id}`}>
            Rankings
          </Link>
          {!p.is_synthetic && (
            <button className="btn-ghost" onClick={() => remove.mutate()} disabled={remove.isPending}>
              Delete & remove data
            </button>
          )}
        </div>
      </div>

      {analyze.error && <p className="text-sm text-amber-300">{(analyze.error as Error).message}</p>}

      <div className="grid gap-4 md:grid-cols-2">
        <a className="panel block p-4 text-sm text-champagne-400" href={p.linkedin_url} target="_blank" rel="noreferrer">
          LinkedIn source →
        </a>
        <a className="panel block p-4 text-sm text-champagne-400" href={p.instagram_url} target="_blank" rel="noreferrer">
          Instagram source →
        </a>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {p.sources.map((s) => (
          <div key={s.id} className="panel p-5">
            <div className="flex items-center justify-between">
              <h3 className="text-sm uppercase tracking-[0.16em] text-ivory-300/60">{s.source_type}</h3>
              <StatusBadge label={s.acquisition_status} />
            </div>
            <p className="mt-2 text-xs text-ivory-300/45">Method: {s.acquisition_method}</p>
            <p className="mt-3 text-sm text-ivory-200/70">{s.verification_notes}</p>
            <p className="mt-3 border-t border-ivory-200/10 pt-3 text-xs text-ivory-300/40">
              Preview: {s.permitted_content_preview || "(empty — provide authorized text)"}
            </p>
          </div>
        ))}
      </div>

      {!a && !analysis.isFetching && (
        <div className="panel p-6 text-sm text-ivory-300/50">
          No analysis yet. Trigger analysis after permitted content is available.
        </div>
      )}

      {a && (
        <div className="space-y-6">
          <div className="panel p-6">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-display text-2xl text-ivory-50">Summary</h2>
              <StatusBadge label={a.status} />
              <StatusBadge label={a.model_name} tone={a.is_demo || a.model_name.includes("deterministic") ? "demo" : "good"} />
            </div>
            <p className="mt-4 text-base leading-relaxed text-ivory-100/85">{a.summary}</p>
            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              {Object.entries(a.confidence_by_attribute || {}).map(([k, v]) => (
                <ConfidenceBar key={k} label={k} value={Number(v)} />
              ))}
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <EvidenceList title="Interests" items={a.interests} />
            <EvidenceList title="Hobbies" items={a.hobbies} />
            <EvidenceList title="Explicit preferences" items={a.explicitly_stated_preferences} />
            <EvidenceList title="Lifestyle clues" items={a.lifestyle_clues} />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="panel p-5">
              <h3 className="text-sm uppercase tracking-[0.16em] text-ivory-300/55">Unknown / missing</h3>
              <ul className="mt-3 space-y-2 text-sm text-ivory-200/70">
                {(a.missing_information || []).map((x) => (
                  <li key={x}>• {x}</li>
                ))}
                {(a.uncertainty_notes || []).map((x) => (
                  <li key={x} className="text-ivory-300/45">• {x}</li>
                ))}
              </ul>
            </div>
            <div className="panel p-5">
              <h3 className="text-sm uppercase tracking-[0.16em] text-ivory-300/55">Contradictions</h3>
              <ul className="mt-3 space-y-2 text-sm text-ivory-200/70">
                {(a.contradictions || []).length === 0 && <li className="text-ivory-300/40">None flagged</li>}
                {(a.contradictions || []).map((x) => (
                  <li key={x}>• {x}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function EvidenceList({
  title,
  items,
}: {
  title: string;
  items: { value: string; evidence?: string; source_type?: string; confidence?: number }[];
}) {
  return (
    <div className="panel p-5">
      <h3 className="text-sm uppercase tracking-[0.16em] text-ivory-300/55">{title}</h3>
      <ul className="mt-3 space-y-3">
        {(items || []).length === 0 && <li className="text-sm text-ivory-300/35">No grounded evidence</li>}
        {(items || []).map((item, i) => (
          <li key={`${item.value}-${i}`} className="border-b border-ivory-200/5 pb-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm text-ivory-100">{item.value}</span>
              {item.source_type && <StatusBadge label={item.source_type} />}
            </div>
            {item.evidence && (
              <p className="mt-1 text-xs italic text-ivory-300/45">“{item.evidence}”</p>
            )}
            {typeof item.confidence === "number" && (
              <div className="mt-2">
                <ConfidenceBar value={item.confidence} />
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
