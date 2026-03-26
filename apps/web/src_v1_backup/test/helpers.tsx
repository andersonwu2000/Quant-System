import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { I18nContext } from "@core/i18n";
import { en } from "@core/i18n/locales/en";
import { AuthProvider } from "@core/auth";

const defaultI18n = {
  t: en,
  lang: "en" as const,
  setLang: () => {},
};

export function renderWithProviders(
  ui: ReactNode,
  { route = "/" } = {},
) {
  return render(
    <I18nContext.Provider value={defaultI18n}>
      <AuthProvider>
        <MemoryRouter initialEntries={[route]}>
          {ui}
        </MemoryRouter>
      </AuthProvider>
    </I18nContext.Provider>,
  );
}
