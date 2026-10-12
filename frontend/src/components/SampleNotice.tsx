import { Link } from "react-router-dom";

/** Shown wherever the synthetic placeholder sample stands in for real people. */
export function SampleNotice() {
  return (
    <div className="rounded-sm border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100/90">
      <strong className="font-medium">Synthetic sample.</strong> No real people have been added
      yet, so these are invented placeholder profiles.{" "}
      <Link className="text-champagne-400 underline" to="/app">
        Paste LinkedIn + Instagram links
      </Link>{" "}
      to replace them.
    </div>
  );
}
