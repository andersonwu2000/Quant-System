import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, Briefcase, Brain, FlaskConical,
  ShieldAlert, Settings, ListOrdered,
} from "lucide-react";
import { useT } from "@core/i18n";

export function Sidebar() {
  const { t } = useT();

  const links = [
    { to: "/", icon: LayoutDashboard, label: t.nav.dashboard },
    { to: "/portfolio", icon: Briefcase, label: t.nav.portfolio },
    { to: "/strategies", icon: Brain, label: t.nav.strategies },
    { to: "/orders", icon: ListOrdered, label: t.nav.orders },
    { to: "/backtest", icon: FlaskConical, label: t.nav.backtest },
    { to: "/risk", icon: ShieldAlert, label: t.nav.risk },
    { to: "/settings", icon: Settings, label: t.nav.settings },
  ];

  return (
    <aside className="w-56 bg-surface-dark border-r border-surface-light flex flex-col h-screen sticky top-0">
      <div className="px-5 py-6 border-b border-surface-light">
        <h1 className="text-lg font-bold tracking-tight">{t.appName}</h1>
        <p className="text-xs text-slate-500 mt-0.5">{t.appVersion}</p>
      </div>
      <nav className="flex-1 py-3 px-3 space-y-0.5">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-blue-500/15 text-blue-400"
                  : "text-slate-400 hover:text-slate-200 hover:bg-surface"
              }`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
