import { Modal } from "./Modal";

interface ConfirmModalProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "warning" | "default";
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}

const CONFIRM_STYLES: Record<string, string> = {
  danger:
    "bg-red-600 hover:bg-red-700 focus:ring-red-500 text-white",
  warning:
    "bg-amber-500 hover:bg-amber-600 focus:ring-amber-400 text-white",
  default:
    "bg-blue-600 hover:bg-blue-700 focus:ring-blue-500 text-white",
};

export function ConfirmModal({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "default",
  onConfirm,
  onCancel,
  loading = false,
}: ConfirmModalProps) {
  return (
    <Modal open={open} onClose={onCancel} title={title}>
      <p className="text-sm text-slate-600 dark:text-slate-300 mb-6">{message}</p>

      <div className="flex justify-end gap-3">
        <button
          onClick={onCancel}
          disabled={loading}
          className="px-4 py-2 rounded-lg text-sm font-medium text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-surface-light hover:bg-slate-200 dark:hover:bg-surface-light/80 transition-colors"
        >
          {cancelLabel}
        </button>
        <button
          onClick={onConfirm}
          disabled={loading}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed ${CONFIRM_STYLES[variant]}`}
        >
          {loading ? "..." : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
