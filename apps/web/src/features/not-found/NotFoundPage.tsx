import { Link } from "react-router-dom";
import { useT } from "@core/i18n";

export function NotFoundPage() {
  const { t } = useT();
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="text-center space-y-4">
        <p className="text-6xl font-bold text-slate-600">404</p>
        <p className="text-slate-400">{t.notFound.title}</p>
        <Link
          to="/"
          className="inline-block px-6 py-2.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors"
        >
          {t.notFound.backLink}
        </Link>
      </div>
    </div>
  );
}
