import { Plus, X } from "lucide-react";

interface Props {
  params: Record<string, unknown>;
  onChange: (params: Record<string, unknown>) => void;
}

export function ParamsEditor({ params, onChange }: Props) {
  const entries = Object.entries(params);

  const addParam = () => {
    const key = `param_${entries.length + 1}`;
    onChange({ ...params, [key]: "" });
  };

  const removeParam = (key: string) => {
    const next = { ...params };
    delete next[key];
    onChange(next);
  };

  const updateKey = (oldKey: string, newKey: string) => {
    if (newKey === oldKey) return;
    const next: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(params)) {
      next[k === oldKey ? newKey : k] = v;
    }
    onChange(next);
  };

  const updateValue = (key: string, raw: string) => {
    const num = Number(raw);
    onChange({ ...params, [key]: raw === "" ? "" : isNaN(num) ? raw : num });
  };

  return (
    <div className="col-span-full space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-400">Strategy Parameters</span>
        <button
          type="button"
          onClick={addParam}
          className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
        >
          <Plus size={12} /> Add
        </button>
      </div>
      {entries.map(([key, value]) => (
        <div key={key} className="flex gap-2">
          <input
            value={key}
            onChange={(e) => updateKey(key, e.target.value)}
            placeholder="key"
            className="w-1/3 bg-surface-dark border border-surface-light rounded-lg px-3 py-1.5 text-sm"
          />
          <input
            value={String(value)}
            onChange={(e) => updateValue(key, e.target.value)}
            placeholder="value"
            className="flex-1 bg-surface-dark border border-surface-light rounded-lg px-3 py-1.5 text-sm"
          />
          <button
            type="button"
            onClick={() => removeParam(key)}
            className="text-slate-500 hover:text-red-400 transition-colors"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
