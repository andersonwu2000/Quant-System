import { useState, useMemo, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";
import { useT } from "@core/i18n";

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

const VIRTUAL_ROW_HEIGHT = 40;
const VIRTUAL_THRESHOLD = 100;
const VIRTUAL_CONTAINER_HEIGHT = 600;

export function DataTable<T>({
  columns,
  data,
  keyFn,
  pageSize = 25,
  emptyMessage,
}: Props<T>) {
  const { t } = useT();
  const empty = emptyMessage ?? t.common.noData;
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

  // Virtualize when showing all rows (no pagination) and row count exceeds threshold.
  // If paginated (totalPages > 1), use pagination instead of virtualization.
  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const isPaginated = totalPages > 1;
  const shouldVirtualize = !isPaginated && sorted.length > VIRTUAL_THRESHOLD;

  const clamped = Math.min(page, totalPages - 1);
  const paged = isPaginated
    ? sorted.slice(clamped * pageSize, (clamped + 1) * pageSize)
    : sorted;

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
    setPage(0);
  };

  const sortIcon = (col: string) => {
    if (sortKey !== col)
      return <ChevronsUpDown size={12} className="text-slate-600" />;
    return sortDir === "asc" ? (
      <ChevronUp size={12} />
    ) : (
      <ChevronDown size={12} />
    );
  };

  const headerRow = (
    <thead>
      <tr className="text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-surface-light">
        {columns.map((col) => (
          <th
            key={col.key}
            role="columnheader"
            aria-sort={
              col.sortValue
                ? sortKey === col.key
                  ? sortDir === "asc" ? "ascending" : "descending"
                  : "none"
                : undefined
            }
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
              {col.sortValue && sortIcon(col.key)}
            </span>
          </th>
        ))}
      </tr>
    </thead>
  );

  return (
    <div className="bg-white dark:bg-surface rounded-xl p-5 overflow-x-auto shadow-sm dark:shadow-none">
      {shouldVirtualize ? (
        <VirtualizedBody
          columns={columns}
          data={sorted}
          keyFn={keyFn}
          headerRow={headerRow}
        />
      ) : (
        <table className="w-full text-sm" role="table">
          {headerRow}
          <tbody>
            {paged.map((row) => (
              <tr
                key={keyFn(row)}
                className="border-b border-slate-100 dark:border-surface-light/50 hover:bg-slate-50 dark:hover:bg-surface-light/30"
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
      )}
      {sorted.length === 0 && (
        <p className="text-center text-slate-400 dark:text-slate-500 py-8">{empty}</p>
      )}
      {isPaginated && (
        <div className="flex items-center justify-between mt-4 text-sm text-slate-500 dark:text-slate-400">
          <span>{sorted.length} {t.common.rows}</span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(Math.max(0, clamped - 1))}
              disabled={clamped === 0}
              aria-label="Previous page"
              className="px-2 py-1 rounded hover:bg-slate-100 dark:hover:bg-surface-light disabled:opacity-30 transition-colors"
            >
              &lt;
            </button>
            <span>
              {clamped + 1} / {totalPages}
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages - 1, clamped + 1))}
              disabled={clamped >= totalPages - 1}
              aria-label="Next page"
              className="px-2 py-1 rounded hover:bg-slate-100 dark:hover:bg-surface-light disabled:opacity-30 transition-colors"
            >
              &gt;
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Virtualized table body — rendered only when row count > threshold   */
/* ------------------------------------------------------------------ */

interface VirtualizedBodyProps<T> {
  columns: Column<T>[];
  data: T[];
  keyFn: (row: T) => string;
  headerRow: React.ReactNode;
}

function VirtualizedBody<T>({
  columns,
  data,
  keyFn,
  headerRow,
}: VirtualizedBodyProps<T>) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: data.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => VIRTUAL_ROW_HEIGHT,
    overscan: 20,
  });

  const virtualItems = virtualizer.getVirtualItems();
  const totalSize = virtualizer.getTotalSize();
  const startPad = virtualItems.length > 0 ? (virtualItems[0]?.start ?? 0) : 0;
  const lastItem = virtualItems.length > 0 ? virtualItems[virtualItems.length - 1] : undefined;
  const endPad = lastItem ? totalSize - (lastItem.end ?? 0) : 0;

  return (
    <div
      ref={parentRef}
      style={{ height: VIRTUAL_CONTAINER_HEIGHT, overflow: "auto" }}
    >
      <table className="w-full text-sm" role="table">
        {headerRow}
        <tbody>
          {/* Spacer row before visible items */}
          {virtualItems.length > 0 && (
            <tr aria-hidden>
              <td
                colSpan={columns.length}
                style={{ height: startPad, padding: 0, border: 0 }}
              />
            </tr>
          )}
          {virtualItems.map((virtualRow) => {
            const row = data[virtualRow.index];
            return (
              <tr
                key={keyFn(row)}
                className="border-b border-slate-100 dark:border-surface-light/50 hover:bg-slate-50 dark:hover:bg-surface-light/30"
                style={{ height: VIRTUAL_ROW_HEIGHT }}
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
            );
          })}
          {/* Spacer row after visible items */}
          {virtualItems.length > 0 && (
            <tr aria-hidden>
              <td
                colSpan={columns.length}
                style={{ height: endPad, padding: 0, border: 0 }}
              />
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
