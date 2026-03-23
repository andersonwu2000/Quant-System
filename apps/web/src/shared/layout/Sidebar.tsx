import { useState, useEffect } from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, Briefcase, Brain, FlaskConical,
  ShieldAlert, Settings, ListOrdered, LogOut,
  ChevronLeft, ChevronRight,
} from "lucide-react";
import { useT } from "@core/i18n";

export function Sidebar({ onLogout }: { onLogout?: () => void }) {
  const { t } = useT();
  const [collapsed, setCollapsed] = useState(() => window.innerWidth < 768);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 767px)");
    const handler = (e: MediaQueryListEvent) => setCollapsed(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

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
    <aside className={`${collapsed ? "w-16" : "w-56"} bg-surface-dark border-r border-surface-light flex flex-col h-screen sticky top-0 transition-all duration-200`}>
      <div className={`px-5 py-6 border-b border-surface-light ${collapsed ? "px-3" : ""}`}>
        {collapsed ? (
          <h1 className="text-lg font-bold text-center">Q</h1>
        ) : (
          <>
            <h1 className="text-lg font-bold tracking-tight">{t.appName}</h1>
            <p className="text-xs text-slate-500 mt-0.5">{t.appVersion}</p>
          </>
        )}
      </div>
      <nav className="flex-1 py-3 px-2 space-y-0.5">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              `flex items-center ${collapsed ? "justify-center" : "gap-3 px-3"} py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-blue-500/15 text-blue-400"
                  : "text-slate-400 hover:text-slate-200 hover:bg-surface"
              }`
            }
          >
            <Icon size={18} />
            {!collapsed && label}
          </NavLink>
        ))}
      </nav>
      <div className="px-2 pb-2 space-y-1">
        {onLogout && (
          <button
            onClick={onLogout}
            title={collapsed ? "Logout" : undefined}
            className={`flex items-center ${collapsed ? "justify-center" : "gap-3 px-3"} py-2.5 rounded-lg text-sm font-medium text-slate-400 hover:text-red-400 hover:bg-surface transition-colors w-full`}
          >
            <LogOut size={18} />
            {!collapsed && "Logout"}
          </button>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center justify-center py-2 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-surface transition-colors w-full"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
    </aside>
  );
}
