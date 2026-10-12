export function ConfidenceBar({ value, label }: { value: number; label?: string }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className="space-y-1">
      {label && (
        <div className="flex justify-between text-[11px] uppercase tracking-[0.14em] text-ivory-300/50">
          <span>{label}</span>
          <span>{pct}%</span>
        </div>
      )}
      <div className="h-1.5 overflow-hidden rounded-full bg-ink-700">
        <div
          className="h-full rounded-full bg-gradient-to-r from-champagne-600 to-champagne-400 transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
