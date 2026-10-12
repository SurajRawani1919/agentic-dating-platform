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
          {settings.data?.notes?.map((n) => (
            <p key={n}>• {n}</p>
          ))}
        </div>
      </div>

      <div className="panel p-6">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="font-display text-2xl text-ivory-50">Profile readers</h2>
          <StatusBadge
            label={settings.data?.scraping_enabled ? "Reading live from links" : "Disabled"}
            tone={settings.data?.scraping_enabled ? "good" : "warn"}
          />
          <StatusBadge label={settings.data?.apify_configured ? "Apify fallback on" : "Apify fallback off"} />
        </div>
        <ul className="mt-4 space-y-2 text-sm text-ivory-200/70">
          {(settings.data?.profile_readers ?? []).map((r) => (
            <li key={r}>• {r}</li>
          ))}
        </ul>
      </div>

      <div className="panel p-6 text-sm text-ivory-200/70">
        <h2 className="font-display text-2xl text-ivory-50">How the agents run</h2>
        <ol className="mt-4 list-decimal space-y-2 pl-5">
          <li>Paste a LinkedIn link and a public Instagram link. Both pages are read live.</li>
          <li>The person's agent analyzes them: needs, hobbies, interests and other qualities.</li>
          <li>Start dating: every agent dates every other agent and files a private verdict.</li>
          <li>
            With <code className="text-champagne-400">LLM_API_KEY</code> set on the server the agents are
            LLM-driven; without it, built-in rule-based agents do the same job and are labeled as such.
          </li>
        </ol>
      </div>
    </div>
  );
}
