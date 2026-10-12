import type { EvidenceItem } from "../types";
import { ConfidenceBar } from "./ConfidenceBar";
import { StatusBadge } from "./StatusBadge";

/** A titled list of claims, each with the quote it was drawn from. */
export function EvidenceList({
  title,
  subtitle,
  items,
  emphasis = false,
  empty = "Nothing on either profile supports a claim here.",
}: {
  title: string;
  subtitle?: string;
  items: EvidenceItem[];
  emphasis?: boolean;
  empty?: string;
}) {
  return (
    <div className={`panel p-5 ${emphasis ? "border-champagne-500/30" : ""}`}>
      <div className="flex items-baseline justify-between gap-3">
        <h3
          className={
            emphasis
              ? "font-display text-2xl text-ivory-50"
              : "text-sm uppercase tracking-[0.16em] text-ivory-300/55"
          }
        >
          {title}
        </h3>
        <span className="text-xs text-ivory-300/35">{(items || []).length}</span>
      </div>
      {subtitle && <p className="mt-1 text-xs text-ivory-300/45">{subtitle}</p>}
      <ul className="mt-3 space-y-3">
        {(items || []).length === 0 && <li className="text-sm text-ivory-300/35">{empty}</li>}
        {(items || []).map((item, i) => (
          <li key={`${item.value}-${i}`} className="border-b border-ivory-200/5 pb-3 last:border-0">
            <div className="flex items-start justify-between gap-2">
              <span className={emphasis ? "text-base text-ivory-50" : "text-sm text-ivory-100"}>
                {item.value}
              </span>
              {item.source_type && <StatusBadge label={item.source_type} />}
            </div>
            {item.evidence && (
              <p className="mt-1 text-xs italic text-ivory-300/45">“{item.evidence}”</p>
            )}
            {item.why && <p className="mt-1 text-xs text-champagne-400/80">{item.why}</p>}
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
