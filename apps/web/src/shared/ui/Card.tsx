import type { ReactNode } from "react";

const base = "bg-slate-50 dark:bg-surface rounded-xl border border-slate-200 dark:border-transparent shadow-sm dark:shadow-none";

export function Card({ className = "", children, ...rest }: { className?: string; children: ReactNode } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`${base} ${className}`} {...rest}>
      {children}
    </div>
  );
}
