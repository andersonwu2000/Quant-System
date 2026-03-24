import { useState, useEffect } from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, Briefcase, Brain, FlaskConical,
  Microscope, ShieldAlert, Settings, ListOrdered, LogOut,
  ChevronLeft, ChevronRight, Users,
} from "lucide-react";
import { useT } from "@core/i18n";
import { useAuth } from "@core/auth";
import { ROLE_BADGE_COLORS } from "@shared/ui";

export function Sidebar({ onLogout }: { onLogout?: () => void }) {
  const { t } = useT();
  const { role, hasRole } = useAuth();
  const [collapsed, setCollapsed] = useState(() => window.matchMedia("(max-width: 767px)").matches);

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
    { to: "/alpha", icon: Microscope, label: t.nav.alpha },
    { to: "/risk", icon: ShieldAlert, label: t.nav.risk },
    ...(hasRole("admin") ? [{ to: "/admin", icon: Users, label: t.nav.admin }] : []),
    { to: "/settings", icon: Settings, label: t.nav.settings },
  ];

  return (
    <aside className={`${collapsed ? "w-16" : "w-56"} bg-slate-50 dark:bg-surface-dark border-r border-slate-200 dark:border-surface-light flex flex-col h-screen sticky top-0 transition-all duration-200`}>
      <div className={`px-5 py-6 border-b border-slate-200 dark:border-surface-light ${collapsed ? "px-3" : ""}`}>
        {collapsed ? (
          <h1 className="text-xl font-bold text-center">Q</h1>
        ) : (
          <>
            <h1 className="text-xl font-bold tracking-tight">{t.appName}</h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{t.appVersion}</p>
            <span className={`inline-block mt-1.5 px-2 py-0.5 rounded text-xs font-semibold ${ROLE_BADGE_COLORS[role]}`}>
              {t.common.roles[role]}
            </span>
          </>
        )}
      </div>
      <nav role="navigation" aria-label="Main navigation" className="flex-1 py-3 px-2 space-y-0.5">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              `flex items-center ${collapsed ? "justify-center" : "gap-3 px-3"} py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-blue-500/15 text-blue-600 dark:text-blue-400"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-surface"
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
            title={collapsed ? t.common.logout : undefined}
            className={`flex items-center ${collapsed ? "justify-center" : "gap-3 px-3"} py-2.5 rounded-lg text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-red-500 dark:hover:text-red-400 hover:bg-slate-100 dark:hover:bg-surface transition-colors w-full`}
          >
            <LogOut size={18} />
            {!collapsed && t.common.logout}
          </button>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="flex items-center justify-center py-2 rounded-lg text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-surface transition-colors w-full"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
    </aside>
  );
}
