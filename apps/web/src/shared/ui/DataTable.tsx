import { useState, useMemo } from "react";
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";

export interface Column<T> {
  key: string;
  label: string;
  align?: "left" | "right" | "center";
  render: (row: T) => React.ReactNode;
  sortValue?: (row: T) => string | number;
}

interface Props<T> {
  columns: Column<T>[];
  data: T[];
  keyFn: (row: T) => string;
  pageSize?: number;
  emptyMessage?: string;
}

export function DataTable<T>({
  columns,
  data,
  keyFn,
  pageSize = 25,
  emptyMessage = "No data",
}: Props<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(0);

  const sorted = useMemo(() => {
    if (!sortKey) return data;
    const col = columns.find((c) => c.key === sortKey);
    if (!col?.sortValue) return data;
    const fn = col.sortValue;
    return [...data].sort((a, b) => {
      const va = fn(a);
      const vb = fn(b);
      const cmp = va < vb ? -1 : va > vb ? 1 : 0;
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [data, sortKey, sortDir, columns]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const clamped = Math.min(page, totalPages - 1);
  const paged = sorted.slice(clamped * pageSize, (clamped + 1) * pageSize);

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
    setPage(0);
  };

  const SortIcon = ({ col }: { col: string }) => {
    if (sortKey !== col)
      return <ChevronsUpDown size={12} className="text-slate-600" />;
    return sortDir === "asc" ? (
      <ChevronUp size={12} />
    ) : (
      <ChevronDown size={12} />
    );
  };

  return (
    <div className="bg-surface rounded-xl p-5 overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-slate-500 border-b border-surface-light">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`py-2 ${
                  col.align === "right" ? "text-right" : "text-left"
                } ${
                  col.sortValue
                    ? "cursor-pointer select-none hover:text-slate-300 transition-colors"
                    : ""
                }`}
                onClick={col.sortValue ? () => handleSort(col.key) : undefined}
              >
                <span className="inline-flex items-center gap-1">
                  {col.label}
                  {col.sortValue && <SortIcon col={col.key} />}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {paged.map((row) => (
            <tr
              key={keyFn(row)}
              className="border-b border-surface-light/50 hover:bg-surface-light/30"
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={`py-2 ${
                    col.align === "right" ? "text-right" : ""
                  }`}
                >
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {sorted.length === 0 && (
        <p className="text-center text-slate-500 py-8">{emptyMessage}</p>
      )}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4 text-sm text-slate-400">
          <span>{sorted.length} rows</span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(Math.max(0, clamped - 1))}
              disabled={clamped === 0}
              className="px-2 py-1 rounded hover:bg-surface-light disabled:opacity-30 transition-colors"
            >
              &lt;
            </button>
            <span>
              {clamped + 1} / {totalPages}
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages - 1, clamped + 1))}
              disabled={clamped >= totalPages - 1}
              className="px-2 py-1 rounded hover:bg-surface-light disabled:opacity-30 transition-colors"
            >
              &gt;
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
