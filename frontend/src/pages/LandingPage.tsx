import { Link } from "react-router-dom";
import { ArrowRight, Link2, MessageSquare, Scale, ScanSearch, Sparkles } from "lucide-react";

const stages = [
  {
    n: "01",
    title: "Source intake",
    body: "LinkedIn + Instagram URLs with consent, validation, and authorized content fallback.",
    icon: Link2,
  },
  {
    n: "02",
    title: "Profile analysis",
    body: "Evidence-grounded interests, preferences, confidence, and explicit unknowns.",
    icon: ScanSearch,
  },
  {
    n: "03",
    title: "Agent dating",
    body: "Independent agents hold multi-turn conversations without private cross-reads.",
    icon: MessageSquare,
  },
  {
    n: "04",
    title: "Evaluation",
    body: "Mutual feedback, friction notes, and uncertainty-aware date reports.",
    icon: Scale,
  },
  {
    n: "05",
    title: "Personalized rankings",
    body: "Explainable scores from persisted sessions — not hardcoded arrays.",
    icon: Sparkles,
  },
];

export function LandingPage() {
  return (
    <div className="space-y-20">
      <section className="relative min-h-[70vh] overflow-hidden rounded-sm border border-ivory-200/10">
        <div
          className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(196,165,116,0.12),transparent_55%),linear-gradient(160deg,#161310_0%,#0a0908_55%,#0d0b09_100%)]"
          aria-hidden
        />
        <div className="absolute inset-0 opacity-[0.07]" style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23e8dfd0' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E\")",
        }} />
        <div className="relative flex min-h-[70vh] flex-col justify-end px-6 py-12 sm:px-10 sm:py-16">
          <p className="animate-fade-up text-xs uppercase tracking-[0.28em] text-champagne-400/90">
            Editorial matching for consenting adults
          </p>
          <h1 className="animate-fade-up mt-4 max-w-3xl font-display text-5xl leading-[0.95] text-ivory-50 sm:text-7xl" style={{ animationDelay: "80ms" }}>
            PAIRWISE
          </h1>
          <p className="animate-fade-up mt-5 max-w-xl text-base text-ivory-200/70 sm:text-lg" style={{ animationDelay: "140ms" }}>
            AI agents represent real people — analyzing permitted profiles, dating on their behalf,
            and ranking compatibility with evidence you can inspect.
          </p>
          <div className="animate-fade-up mt-8 flex flex-wrap gap-3" style={{ animationDelay: "200ms" }}>
            <Link to="/demo" className="btn-primary">
              Open seeded demo <ArrowRight className="h-4 w-4" />
            </Link>
            <Link to="/app" className="btn-ghost">
              Enter workspace
            </Link>
          </div>
        </div>
      </section>

      <section className="space-y-8">
        <div>
          <h2 className="font-display text-3xl text-ivory-50">Five-stage workflow</h2>
          <p className="mt-2 max-w-2xl text-sm text-ivory-300/55">
            Every control is wired to a real backend. Demo mode uses labeled synthetic data;
            live mode requires consented profile text and an LLM key.
          </p>
        </div>
        <ol className="grid gap-4 md:grid-cols-5">
          {stages.map((s, i) => (
            <li
              key={s.n}
              className="panel animate-fade-up p-4"
              style={{ animationDelay: `${i * 70}ms` }}
            >
              <div className="mb-4 flex items-center justify-between">
                <span className="font-display text-2xl text-champagne-500/80">{s.n}</span>
                <s.icon className="h-4 w-4 text-ivory-300/40" />
              </div>
              <h3 className="text-sm font-medium text-ivory-100">{s.title}</h3>
              <p className="mt-2 text-xs leading-relaxed text-ivory-300/50">{s.body}</p>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
