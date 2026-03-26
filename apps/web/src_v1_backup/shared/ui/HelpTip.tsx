import { useState, useRef, useCallback, useEffect } from "react";
import { createPortal } from "react-dom";
import { glossary } from "@core/help";
import { useT } from "@core/i18n";

/**
 * Inline help tooltip for financial terms.
 * Uses the same ℹ icon as InfoTooltip for visual consistency.
 * Renders tooltip via portal to avoid overflow clipping.
 */
export function HelpTip({ term }: { term: string }) {
  const { lang } = useT();
  const entry = glossary[term];
  if (!entry) return null;
  const text = lang === "zh" ? entry.zh : entry.en;

  const [show, setShow] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const ref = useRef<HTMLSpanElement>(null);
  const timeout = useRef<ReturnType<typeof setTimeout>>();

  const handleEnter = useCallback(() => {
    clearTimeout(timeout.current);
    if (!ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const tooltipW = 288; // w-72 = 18rem = 288px
    let left = r.left + r.width / 2 - tooltipW / 2;
    left = Math.max(8, Math.min(left, window.innerWidth - tooltipW - 8));
    let top = r.top - 8; // above the icon
    if (top < 100) top = r.bottom + 8; // flip below if near top
    setPos({ top, left });
    setShow(true);
  }, []);

  const handleLeave = useCallback(() => {
    timeout.current = setTimeout(() => setShow(false), 100);
  }, []);

  // Cleanup timeout on unmount to prevent state update on unmounted component
  useEffect(() => {
    return () => {
      clearTimeout(timeout.current);
    };
  }, []);

  return (
    <>
      <span
        ref={ref}
        onMouseEnter={handleEnter}
        onMouseLeave={handleLeave}
        className="inline-flex items-center ml-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 cursor-help transition-colors"
      >
        <svg width="13" height="13" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" fill="currentColor" aria-hidden="true">
          <path d="M24,2A22,22,0,1,0,46,24,21.9,21.9,0,0,0,24,2Zm0,40A18,18,0,1,1,42,24,18.1,18.1,0,0,1,24,42Z"/>
          <path d="M24,20a2,2,0,0,0-2,2V34a2,2,0,0,0,4,0V22A2,2,0,0,0,24,20Z"/>
          <circle cx="24" cy="14" r="2"/>
        </svg>
      </span>
      {show && pos && createPortal(
        <div
          role="tooltip"
          onMouseEnter={() => clearTimeout(timeout.current)}
          onMouseLeave={handleLeave}
          className="fixed w-72 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 px-3 py-2.5 text-xs text-slate-700 dark:text-slate-200 leading-relaxed shadow-xl z-[70] animate-[fadeIn_0.15s_ease]"
          style={{ top: pos.top, left: pos.left, transform: "translateY(-100%)" }}
        >
          {text}
        </div>,
        document.body,
      )}
    </>
  );
}
