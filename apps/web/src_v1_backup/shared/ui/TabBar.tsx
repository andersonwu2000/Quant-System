import { useRef, useCallback } from "react";

export interface Tab<T extends string> {
  id: T;
  label: string;
  badge?: number;
}

interface TabBarProps<T extends string> {
  tabs: Tab<T>[];
  active: T;
  onChange: (id: T) => void;
}

export function TabBar<T extends string>({ tabs, active, onChange }: TabBarProps<T>) {
  const containerRef = useRef<HTMLDivElement>(null);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight" && e.key !== "Enter") return;

      const currentIndex = tabs.findIndex((t) => t.id === active);
      if (currentIndex === -1) return;

      if (e.key === "Enter") {
        // Focus is on a button; the active tab is already tracked by the focused element
        const focused = document.activeElement as HTMLElement | null;
        const tabId = focused?.getAttribute("data-tab-id") as T | null;
        if (tabId) onChange(tabId);
        return;
      }

      e.preventDefault();
      const nextIndex =
        e.key === "ArrowRight"
          ? (currentIndex + 1) % tabs.length
          : (currentIndex - 1 + tabs.length) % tabs.length;

      onChange(tabs[nextIndex].id);

      // Move focus to the new tab button
      const buttons = containerRef.current?.querySelectorAll<HTMLButtonElement>("[data-tab-id]");
      buttons?.[nextIndex]?.focus();
    },
    [tabs, active, onChange],
  );

  return (
    <div
      ref={containerRef}
      role="tablist"
      className="flex gap-1 bg-slate-100 dark:bg-surface-light p-1 rounded-lg w-fit"
      onKeyDown={handleKeyDown}
    >
      {tabs.map(({ id, label, badge }) => {
        const isActive = active === id;
        return (
          <button
            key={id}
            role="tab"
            data-tab-id={id}
            aria-selected={isActive}
            tabIndex={isActive ? 0 : -1}
            onClick={() => onChange(id)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              isActive
                ? "bg-white dark:bg-surface-dark text-slate-900 dark:text-slate-100 shadow-sm"
                : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
            }`}
          >
            {label}
            {badge != null && badge > 0 && (
              <span className="ml-1.5 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 text-xs font-semibold rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200">
                {badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
