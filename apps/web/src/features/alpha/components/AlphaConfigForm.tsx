import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useT } from "@core/i18n";
import { UniversePicker } from "@feat/backtest/components/UniversePicker";
import { AnimatedSelect } from "@feat/backtest/components/AnimatedSelect";
import type { AlphaRunRequest, AlphaFactorSpec, FactorName } from "@core/api";

const FACTORS: { name: FactorName; defaultDirection: 1 | -1 }[] = [
  { name: "momentum",        defaultDirection:  1 },
  { name: "mean_reversion",  defaultDirection: -1 },
  { name: "volatility",      defaultDirection: -1 },
  { name: "rsi",             defaultDirection: -1 },
  { name: "ma_cross",        defaultDirection:  1 },
  { name: "vpt",             defaultDirection:  1 },
  { name: "reversal",        defaultDirection: -1 },
  { name: "illiquidity",     defaultDirection:  1 },
  { name: "ivol",            defaultDirection: -1 },
  { name: "skewness",        defaultDirection: -1 },
  { name: "max_ret",         defaultDirection: -1 },
];

interface Props {
  onSubmit: (req: AlphaRunRequest) => void;
  running: boolean;
}

export function AlphaConfigForm({ onSubmit, running }: Props) {
  const { t } = useT();
  const [open, setOpen] = useState(true);
  const [selectedFactors, setSelectedFactors] = useState<Partial<Record<FactorName, 1 | -1>>>({
    momentum: 1,
    mean_reversion: -1,
  });
  const [universe, setUniverse] = useState<string[]>([]);
  const [start, setStart] = useState("2020-01-01");
  const [end, setEnd] = useState(() => new Date().toISOString().slice(0, 10));
  const [neutralize, setNeutralize] = useState<AlphaRunRequest["neutralize_method"]>("market");
  const [nQuantiles, setNQuantiles] = useState(5);
  const [holdingPeriod, setHoldingPeriod] = useState(5);
  const [errors, setErrors] = useState<string[]>([]);

  const toggleFactor = (name: FactorName, def: 1 | -1) => {
    setSelectedFactors((prev) => {
      const next = { ...prev };
      if (name in next) { delete next[name]; }
      else { next[name] = def; }
      return next;
    });
  };

  const flipDirection = (name: FactorName) => {
    setSelectedFactors((prev) => ({ ...prev, [name]: prev[name] === 1 ? -1 : 1 }));
  };

  const validate = (): boolean => {
    const errs: string[] = [];
    if (Object.keys(selectedFactors).length === 0) errs.push(t.alpha.errorFactors);
    if (universe.length === 0) errs.push(t.alpha.errorUniverse);
    if (end <= start) errs.push(t.alpha.errorEndDate);
    setErrors(errs);
    return errs.length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    const factors: AlphaFactorSpec[] = (
      Object.entries(selectedFactors) as [FactorName, 1 | -1][]
    ).map(([name, direction]) => ({ name, direction }));
    onSubmit({ factors, universe, start, end, neutralize_method: neutralize, n_quantiles: nQuantiles, holding_period: holdingPeriod });
    setOpen(false);
  };

  const neutralizeOptions = [
    { value: "market",         label: t.alpha.neutralizeMarket },
    { value: "industry",       label: t.alpha.neutralizeIndustry },
    { value: "size",           label: t.alpha.neutralizeSize },
    { value: "industry_size",  label: t.alpha.neutralizeIndustrySize },
  ];

  return (
    <div className="bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-xl shadow-sm">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-5 py-4 text-left"
      >
        <span className="font-semibold text-slate-800 dark:text-slate-100">{t.alpha.factors}</span>
        {open ? <ChevronUp size={18} className="text-slate-400" /> : <ChevronDown size={18} className="text-slate-400" />}
      </button>

      {open && (
        <form onSubmit={handleSubmit} className="px-5 pb-5 space-y-6 border-t border-slate-100 dark:border-surface-light pt-4">

          {/* Factor chips */}
          <div className="flex flex-wrap gap-2">
            {FACTORS.map(({ name, defaultDirection }) => {
              const checked = name in selectedFactors;
              const dir = selectedFactors[name] ?? defaultDirection;
              const label = (t.alpha.factorNames as Record<string, string>)[name] ?? name;
              return (
                <button
                  key={name}
                  type="button"
                  onClick={() => toggleFactor(name, defaultDirection)}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${
                    checked
                      ? "bg-blue-50 dark:bg-blue-500/10 border-blue-300 dark:border-blue-500/40 text-blue-700 dark:text-blue-300"
                      : "bg-slate-50 dark:bg-surface-light border-slate-200 dark:border-surface-light text-slate-600 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-500"
                  }`}
                >
                  {label}
                  {checked && (
                    <span
                      role="button"
                      title={dir === 1 ? t.alpha.directionUp : t.alpha.directionDown}
                      onClick={(e) => { e.stopPropagation(); flipDirection(name); }}
                      className="text-xs px-1 py-0.5 rounded bg-blue-200/60 dark:bg-blue-500/20 hover:bg-blue-300/60 dark:hover:bg-blue-500/30 transition-colors"
                    >
                      {dir === 1 ? "↑" : "↓"}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          <hr className="border-slate-100 dark:border-surface-light" />

          {/* Universe */}
          <UniversePicker value={universe} onChange={setUniverse} />

          {/* Date range */}
          <div className="grid grid-cols-2 gap-3">
            <label className="space-y-1">
              <span className="text-sm text-slate-500 dark:text-slate-400">{t.backtest.start}</span>
              <input type="date" value={start} onChange={(e) => setStart(e.target.value)}
                className="w-full bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm" />
            </label>
            <label className="space-y-1">
              <span className="text-sm text-slate-500 dark:text-slate-400">{t.backtest.end}</span>
              <input type="date" value={end} onChange={(e) => setEnd(e.target.value)}
                className="w-full bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm" />
            </label>
          </div>

          {/* Advanced options */}
          <div className="grid grid-cols-3 gap-3">
            <label className="space-y-1">
              <span className="text-sm text-slate-500 dark:text-slate-400">{t.alpha.neutralize}</span>
              <AnimatedSelect
                value={neutralize ?? "market"}
                options={neutralizeOptions}
                onChange={(v) => setNeutralize(v as AlphaRunRequest["neutralize_method"])}
              />
            </label>
            <label className="space-y-1">
              <span className="text-sm text-slate-500 dark:text-slate-400">{t.alpha.nQuantiles}</span>
              <input type="number" min={3} max={10} value={nQuantiles} onChange={(e) => setNQuantiles(Number(e.target.value))}
                className="w-full bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm" />
            </label>
            <label className="space-y-1">
              <span className="text-sm text-slate-500 dark:text-slate-400">{t.alpha.holdingPeriod}</span>
              <input type="number" min={1} max={60} value={holdingPeriod} onChange={(e) => setHoldingPeriod(Number(e.target.value))}
                className="w-full bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm" />
            </label>
          </div>

          {errors.length > 0 && (
            <ul className="space-y-1">
              {errors.map((e) => (
                <li key={e} className="text-sm text-red-500 dark:text-red-400">{e}</li>
              ))}
            </ul>
          )}

          <button
            type="submit"
            disabled={running}
            className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {running ? t.alpha.running : t.alpha.run}
          </button>
        </form>
      )}
    </div>
  );
}
