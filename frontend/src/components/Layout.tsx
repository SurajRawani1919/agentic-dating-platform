import { NavLink, Outlet } from "react-router-dom";
import { Sparkles } from "lucide-react";

const links = [
  { to: "/", label: "Home" },
  { to: "/app", label: "Add people" },
  { to: "/participants", label: "Profiles" },
  { to: "/dates", label: "Dates" },
  { to: "/rankings", label: "Rankings" },
  { to: "/demo", label: "Demo" },
  { to: "/settings", label: "Settings" },
];

export function Layout() {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-ivory-200/10 bg-ink-950/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <NavLink to="/" className="group flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-sm border border-champagne-500/40 text-champagne-400 transition group-hover:border-champagne-400">
              <Sparkles className="h-4 w-4" />
            </span>
            <div>
              <div className="font-display text-xl leading-none tracking-[0.08em] text-ivory-50">
                PAIRWISE
              </div>
              <div className="mt-1 text-[10px] uppercase tracking-[0.22em] text-champagne-500/80">
                AI agents · real compatibility
              </div>
            </div>
          </NavLink>
          <nav className="hidden items-center gap-1 md:flex">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.to === "/"}
                className={({ isActive }) =>
                  `rounded-sm px-3 py-1.5 text-xs uppercase tracking-[0.16em] transition ${
                    isActive
                      ? "text-champagne-400"
                      : "text-ivory-300/55 hover:text-ivory-100"
                  }`
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex gap-1 overflow-x-auto border-t border-ivory-200/5 px-4 py-2 md:hidden">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === "/"}
              className={({ isActive }) =>
                `whitespace-nowrap rounded-sm px-3 py-1 text-[11px] uppercase tracking-[0.14em] ${
                  isActive ? "bg-ink-800 text-champagne-400" : "text-ivory-300/50"
                }`
              }
            >
              {l.label}
            </NavLink>
          ))}
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12">
        <Outlet />
      </main>
      <footer className="border-t border-ivory-200/10 py-8 text-center text-xs text-ivory-300/40">
        Two sources only: public LinkedIn + public Instagram · Every claim quotes its evidence
      </footer>
    </div>
  );
}
