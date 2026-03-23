function InfoIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" fill="currentColor" aria-hidden="true">
      <path d="M24,2A22,22,0,1,0,46,24,21.9,21.9,0,0,0,24,2Zm0,40A18,18,0,1,1,42,24,18.1,18.1,0,0,1,24,42Z"/>
      <path d="M24,20a2,2,0,0,0-2,2V34a2,2,0,0,0,4,0V22A2,2,0,0,0,24,20Z"/>
      <circle cx="24" cy="14" r="2"/>
    </svg>
  );
}

export function InfoTooltip({ description }: { description: string }) {
  return (
    <span className="relative group inline-flex items-center ml-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 cursor-default">
      <InfoIcon />
      <span className="pointer-events-none absolute left-1/2 -translate-x-1/2 bottom-full mb-2 w-72 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 px-3 py-2 text-xs text-slate-700 dark:text-slate-200 leading-relaxed shadow-xl opacity-0 group-hover:opacity-100 transition-opacity duration-150 z-50">
        {description}
        <span className="absolute left-1/2 -translate-x-1/2 top-full w-0 h-0 border-x-4 border-x-transparent border-t-4 border-t-slate-200 dark:border-t-slate-600" />
      </span>
    </span>
  );
}
