import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";

interface Props {
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
}

export function AnimatedSelect({ value, options, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  const dropRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0, width: 0 });

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        btnRef.current && !btnRef.current.contains(target) &&
        dropRef.current && !dropRef.current.contains(target)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Position the dropdown relative to the button
  const updatePos = useCallback(() => {
    if (!btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    setPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
  }, []);

  useEffect(() => {
    if (!open) return;
    updatePos();
    window.addEventListener("scroll", updatePos, true);
    window.addEventListener("resize", updatePos);
    return () => {
      window.removeEventListener("scroll", updatePos, true);
      window.removeEventListener("resize", updatePos);
    };
  }, [open, updatePos]);

  const current = options.find((o) => o.value === value)?.label ?? value;

  const dropdown = open
    ? createPortal(
        <div
          ref={dropRef}
          className="fixed z-50 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg shadow-xl overflow-y-auto max-h-80"
          style={{ top: pos.top, left: pos.left, width: pos.width }}
        >
          {options.map((o) => (
            <button
              key={o.value}
              type="button"
              onClick={() => { onChange(o.value); setOpen(false); }}
              className={`w-full text-left px-3 py-2 text-sm transition-colors hover:bg-slate-100 dark:hover:bg-slate-700 ${
                value === o.value ? "text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-500/10" : "text-slate-700 dark:text-slate-200"
              }`}
            >
              {o.label}
            </button>
          ))}
        </div>,
        document.body,
      )
    : null;

  return (
    <div>
      <button
        ref={btnRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm flex items-center justify-between transition-colors hover:border-slate-400 dark:hover:border-slate-500"
      >
        <span>{current}</span>
        <svg
          width="12" height="12" viewBox="0 0 48 48" fill="currentColor"
          className="text-slate-400 transition-transform duration-200 shrink-0"
          style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)" }}
        >
          <path d="M24,32a2,2,0,0,1-1.41-.59l-14-14a2,2,0,0,1,2.82-2.82L24,27.17l12.59-12.58a2,2,0,0,1,2.82,2.82l-14,14A2,2,0,0,1,24,32Z"/>
        </svg>
      </button>
      {dropdown}
    </div>
  );
}
