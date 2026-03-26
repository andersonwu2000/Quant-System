import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { LayoutDashboard, TrendingUp, Shield, FlaskConical, Settings, ChevronLeft, ChevronRight } from 'lucide-react';
import { api } from '../../lib/api';

const NAV_ITEMS = [
  { path: '/', icon: LayoutDashboard, label: '總覽' },
  { path: '/strategy', icon: TrendingUp, label: '策略' },
  { path: '/risk', icon: Shield, label: '風控' },
  { path: '/backtest', icon: FlaskConical, label: '回測' },
  { path: '/settings', icon: Settings, label: '設定' },
];

function LiveDot({ status }: { status: 'ok' | 'warn' | 'error' }) {
  const color = status === 'ok' ? 'bg-emerald-500' : status === 'warn' ? 'bg-amber-500' : 'bg-red-500';
  const pulse = status === 'ok' ? 'animate-pulse-dot' : '';
  return <span className={`inline-block h-2 w-2 rounded-full ${color} ${pulse}`} />;
}

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    refetchInterval: 30_000,
  });
  const connectionStatus: 'ok' | 'warn' | 'error' = healthQuery.isSuccess ? 'ok' : healthQuery.isLoading ? 'warn' : 'error';

  return (
    <aside className={`flex flex-col bg-[#0a0a0a] border-r border-white/10 transition-all duration-200 ${collapsed ? 'w-16' : 'w-56'}`}>
      {/* Logo */}
      <div className="flex h-14 items-center justify-between px-4">
        {!collapsed && <span className="text-sm font-semibold text-white">Quant System</span>}
        <button
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? '展開側邊欄' : '收合側邊欄'}
          className="rounded-md p-1 text-neutral-400 hover:bg-white/5 hover:text-white transition-colors duration-150"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      {/* Nav */}
      <nav role="navigation" className="flex-1 space-y-1 px-2 py-4">
        {NAV_ITEMS.map(({ path, icon: Icon, label }) => {
          const active = location.pathname === path;
          return (
            <Link
              key={path}
              to={path}
              aria-current={active ? 'page' : undefined}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-150 ${
                active
                  ? 'bg-blue-500/10 text-blue-400'
                  : 'text-neutral-400 hover:bg-white/5 hover:text-white'
              }`}
            >
              <Icon size={20} strokeWidth={1.5} />
              {!collapsed && <span>{label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Connection status */}
      <div className="border-t border-white/10 px-4 py-3">
        <div className={`flex items-center ${collapsed ? 'justify-center' : 'gap-3'}`}>
          <LiveDot status={connectionStatus} />
          {!collapsed && <span className="text-xs text-neutral-500">{connectionStatus === 'ok' ? 'Connected' : connectionStatus === 'warn' ? 'Connecting...' : 'Disconnected'}</span>}
        </div>
      </div>
    </aside>
  );
}
