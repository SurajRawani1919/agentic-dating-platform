/** Turns any YouTube share link into its embeddable form. */
function embedUrl(value: string): string | null {
  try {
    const u = new URL(value.trim());
    const host = u.hostname.replace(/^www\./, "");
    let id: string | null = null;
    if (host === "youtu.be") id = u.pathname.split("/")[1] ?? null;
    else if (host.endsWith("youtube.com")) {
      const parts = u.pathname.split("/").filter(Boolean);
      id = u.searchParams.get("v") ?? (["shorts", "embed", "live"].includes(parts[0]) ? parts[1] : null);
    }
    return id ? `https://www.youtube-nocookie.com/embed/${id}` : null;
  } catch {
    return null;
  }
}

/** The walkthrough video. The link is set once on the server (DEMO_VIDEO_URL) so every visitor sees it. */
export function DemoVideo({ url }: { url?: string }) {
  if (!url) return null;
  const src = embedUrl(url);
  return (
    <div className="panel overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-ivory-200/10 px-5 py-3">
        <h2 className="text-xs uppercase tracking-[0.18em] text-ivory-300/60">3-minute walkthrough</h2>
        <a className="text-xs text-champagne-400 hover:underline" href={url} target="_blank" rel="noreferrer">
          Open on YouTube →
        </a>
      </div>
      {src && (
        <div className="aspect-video w-full bg-ink-950">
          <iframe
            className="h-full w-full"
            src={src}
            title="PAIRWISE walkthrough"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        </div>
      )}
    </div>
  );
}
