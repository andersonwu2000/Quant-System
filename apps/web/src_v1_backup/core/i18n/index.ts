import { createContext, useContext } from "react";
import { en, type Translations } from "./locales/en";
import { zh } from "./locales/zh";

export type Lang = "en" | "zh";

export const translations: Record<Lang, Translations> = { en, zh };

export const langLabels: Record<Lang, string> = { en: "English", zh: "繁體中文" };

const STORAGE_KEY = "quant_lang";

export function getSavedLang(): Lang {
  const v = localStorage.getItem(STORAGE_KEY);
  return v === "zh" ? "zh" : "en";
}

export function saveLang(lang: Lang) {
  localStorage.setItem(STORAGE_KEY, lang);
}

export interface I18nContextValue {
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
