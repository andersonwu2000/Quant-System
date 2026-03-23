import { Download } from "lucide-react";

interface Props {
  filename: string;
  headers: string[];
  rows: (string | number)[][];
}

export function ExportButton({ filename, headers, rows }: Props) {
  const handleExport = () => {
    const escape = (v: string | number) => {
      const s = String(v);
      return s.includes(",") || s.includes('"') || s.includes("\n")
        ? `"${s.replace(/"/g, '""')}"`
        : s;
    };
    const csv = [
      headers.map(escape).join(","),
      ...rows.map((r) => r.map(escape).join(",")),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <button
      onClick={handleExport}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-surface transition-colors"
    >
      <Download size={12} /> Export CSV
    </button>
  );
}
