import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";

export function SettingsPage() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-4xl text-ivory-50">Settings</h1>
        <p className="mt-2 text-sm text-ivory-300/55">
          Provider configuration is environment-based. API keys are never exposed to the browser.
        </p>
      </div>

      <div className="panel p-6">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="font-display text-2xl text-ivory-50">LLM provider</h2>
          <StatusBadge
            label={health.data?.llm_configured ? "Configured" : "Not configured"}
            tone={health.data?.llm_configured ? "good" : "warn"}
          />
        </div>
        <dl className="mt-6 grid gap-4 sm:grid-cols-2 text-sm">
          <div>
            <dt className="label">Provider</dt>
            <dd>{String(settings.data?.llm_provider ?? "…")}</dd>
          </div>
          <div>
            <dt className="label">Model</dt>
            <dd>{String(settings.data?.llm_model ?? "—")}</dd>
          </div>
          <div>
            <dt className="label">Max concurrent dates</dt>
            <dd>{String(settings.data?.max_concurrent_dates ?? "—")}</dd>
          </div>
          <div>
            <dt className="label">Default max turns</dt>
            <dd>{String(settings.data?.default_max_turns ?? "—")}</dd>
          </div>
        </dl>
        <div className="mt-6 space-y-2 text-sm text-ivory-300/55">
          {(settings.data?.notes as string[] | undefined)?.map((n) => (
            <p key={n}>• {n}</p>
          ))}
        </div>
      </div>

      <div className="panel p-6 text-sm text-ivory-200/70">
        <h2 className="font-display text-2xl text-ivory-50">Live mode checklist</h2>
        <ol className="mt-4 list-decimal space-y-2 pl-5">
          <li>Set <code className="text-champagne-400">LLM_API_KEY</code> and <code className="text-champagne-400">LLM_PROVIDER</code> in the server <code>.env</code>.</li>
          <li>Restart the API.</li>
          <li>Submit consented LinkedIn + Instagram URLs with authorized profile text when acquisition is unsupported.</li>
          <li>Analyze profiles, then create a <strong>live</strong> dating run.</li>
        </ol>
      </div>
    </div>
  );
}
