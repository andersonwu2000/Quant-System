import { createContext, useContext } from "react";
import { en, type Translations } from "./locales/en";
import { zh } from "./locales/zh";

export type Lang = "en" | "zh";
export const translations: Record<Lang, Translations> = { en, zh };

interface I18nContextValue {
  t: Translations;
  lang: Lang;
  setLang: (lang: Lang) => void;
}

export const I18nContext = createContext<I18nContextValue>({
  t: en,
  lang: "en",
  setLang: () => {},
});

export function useT() {
  return useContext(I18nContext);
}
