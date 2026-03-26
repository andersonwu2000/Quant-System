import { useState } from "react";
import { useT } from "@core/i18n";
import { TOC } from "./types";
import { ChevronDown, ChevronRight } from "lucide-react";

import { ChapterOverview } from "./chapters/ChapterOverview";
import { ChapterAlpha } from "./chapters/ChapterAlpha";
import { ChapterBacktest } from "./chapters/ChapterBacktest";
import { ChapterAllocation } from "./chapters/ChapterAllocation";
import { ChapterPaperTrading } from "./chapters/ChapterPaperTrading";
import { ChapterRisk } from "./chapters/ChapterRisk";
import { ChapterFAQ } from "./chapters/ChapterFAQ";

const CHAPTER_COMPONENTS: Record<string, React.FC<{ section?: string }>> = {
  overview: ChapterOverview,
  alpha: ChapterAlpha,
  backtest: ChapterBacktest,
  allocation: ChapterAllocation,
  "paper-trading": ChapterPaperTrading,
  risk: ChapterRisk,
  faq: ChapterFAQ,
};

export function GuidePage() {
  const { lang } = useT();
  const [activeChapter, setActiveChapter] = useState("overview");
  const [activeSection, setActiveSection] = useState("what-is-this");
  const [expandedChapters, setExpandedChapters] = useState<Set<string>>(new Set(["overview"]));

  const toggleChapter = (id: string) => {
    setExpandedChapters((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectSection = (chapterId: string, sectionId: string) => {
    setActiveChapter(chapterId);
    setActiveSection(sectionId);
    setExpandedChapters((prev) => new Set(prev).add(chapterId));
    // Scroll content to top
    document.getElementById("guide-content")?.scrollTo(0, 0);
  };

  const ChapterComponent = CHAPTER_COMPONENTS[activeChapter];
  const t = (titleEn: string, titleZh: string) => lang === "zh" ? titleZh : titleEn;

  return (
    <div className="flex h-[calc(100vh-theme(spacing.6)*2)] max-w-7xl mx-auto gap-0 rounded-xl overflow-hidden border border-slate-200 dark:border-surface-light bg-white dark:bg-surface-dark">
      {/* Left sidebar TOC */}
      <nav className="w-64 shrink-0 border-r border-slate-200 dark:border-surface-light overflow-y-auto py-4 bg-slate-50 dark:bg-surface-dark">
        {TOC.map((chapter) => {
          const isExpanded = expandedChapters.has(chapter.id);
          return (
            <div key={chapter.id}>
              <button
                onClick={() => {
                  toggleChapter(chapter.id);
                  selectSection(chapter.id, chapter.sections[0].id);
                }}
                className={`w-full flex items-center gap-2 px-4 py-2.5 text-sm font-semibold transition-colors ${
                  activeChapter === chapter.id
                    ? "text-blue-600 dark:text-blue-400"
                    : "text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-slate-100"
                }`}
              >
                {isExpanded ? <ChevronDown size={14} className="shrink-0" /> : <ChevronRight size={14} className="shrink-0" />}
                {t(chapter.titleEn, chapter.titleZh)}
              </button>
              {isExpanded && (
                <div className="ml-6 border-l border-slate-200 dark:border-surface-light">
                  {chapter.sections.map((section) => (
                    <button
                      key={section.id}
                      onClick={() => selectSection(chapter.id, section.id)}
                      className={`block w-full text-left pl-4 pr-4 py-1.5 text-xs transition-colors ${
                        activeChapter === chapter.id && activeSection === section.id
                          ? "text-blue-600 dark:text-blue-400 font-medium border-l-2 border-blue-500 -ml-px"
                          : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                      }`}
                    >
                      {t(section.titleEn, section.titleZh)}
                    </button>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* Right content area */}
      <div id="guide-content" className="flex-1 overflow-y-auto p-8">
        {ChapterComponent && <ChapterComponent section={activeSection} />}
      </div>
    </div>
  );
}
