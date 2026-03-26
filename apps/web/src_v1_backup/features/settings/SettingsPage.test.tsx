import { screen, waitFor, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "@test/helpers";
import { SettingsPage } from "./SettingsPage";
import { systemApi } from "./api";

vi.mock("./api", () => ({
  systemApi: {
    status: vi.fn(),
  },
}));

vi.mock("@core/api", () => ({
  isAuthenticated: vi.fn().mockReturnValue(false),
  login: vi.fn(),
  logout: vi.fn(),
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  ApiError: class ApiError extends Error {},
}));

vi.mock("@quant/shared", async () => {
  const actual = await vi.importActual("@quant/shared");
  return {
    ...actual,
    auth: { changePassword: vi.fn() },
  };
});

vi.mock("@core/utils", async () => {
  const actual = await vi.importActual("@core/utils");
  return {
    ...actual,
    translateApiError: (msg: string) => msg,
  };
});

describe("SettingsPage", () => {
  beforeEach(async () => {
    vi.resetAllMocks();
    const { isAuthenticated } = await import("@core/api");
    vi.mocked(isAuthenticated).mockReturnValue(false);
  });

  it("renders page title", () => {
    vi.mocked(systemApi.status).mockReturnValue(new Promise(() => {}));

    renderWithProviders(<SettingsPage />);
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("shows login hint when not authenticated", () => {
    vi.mocked(systemApi.status).mockReturnValue(new Promise(() => {}));

    renderWithProviders(<SettingsPage />);
    expect(screen.getByText(/Please login with your/)).toBeInTheDocument();
  });

  it("renders collapsible section headers", () => {
    vi.mocked(systemApi.status).mockReturnValue(new Promise(() => {}));

    renderWithProviders(<SettingsPage />);
    // Login, Language, Theme, System Status sections exist
    expect(screen.getByText("Language")).toBeInTheDocument();
    expect(screen.getByText("Theme")).toBeInTheDocument();
    expect(screen.getByText("System Status")).toBeInTheDocument();
  });

  it("expands login section and shows save button", () => {
    vi.mocked(systemApi.status).mockReturnValue(new Promise(() => {}));

    renderWithProviders(<SettingsPage />);
    // Click the login section header to expand
    fireEvent.click(screen.getByText("Login"));

    expect(screen.getByText("Save")).toBeInTheDocument();
  });

  it("expands language section and shows language options", () => {
    vi.mocked(systemApi.status).mockReturnValue(new Promise(() => {}));

    renderWithProviders(<SettingsPage />);
    fireEvent.click(screen.getByText("Language"));

    expect(screen.getByText("English")).toBeInTheDocument();
    expect(screen.getByText("繁體中文")).toBeInTheDocument();
  });
});
