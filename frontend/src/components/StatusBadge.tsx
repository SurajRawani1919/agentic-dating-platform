export function StatusBadge({
  label,
  tone = "neutral",
}: {
  label: string;
  tone?: "neutral" | "good" | "warn" | "demo";
}) {
  const tones = {
    neutral: "border-ivory-200/20 text-ivory-300/70",
    good: "border-emerald-500/30 text-emerald-300/80",
    warn: "border-amber-500/30 text-amber-200/80",
    demo: "border-champagne-500/40 text-champagne-400",
  };
  return (
    <span
      className={`inline-flex rounded-sm border px-2 py-0.5 text-[10px] uppercase tracking-[0.16em] ${tones[tone]}`}
    >
      {label}
    </span>
  );
}
