import { screen, waitFor } from "@testing-library/react";
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
  ApiError: class ApiError extends Error {},
}));

const mockStatus = {
  mode: "paper",
  uptime_seconds: 7200,
  strategies_running: 2,
  data_source: "yahoo",
  database: "connected",
};

describe("SettingsPage", () => {
  beforeEach(async () => {
    vi.resetAllMocks();
    // Restore isAuthenticated mock default
    const { isAuthenticated } = await import("@core/api");
    vi.mocked(isAuthenticated).mockReturnValue(false);
  });

  it("renders API key input field", () => {
    vi.mocked(systemApi.status).mockReturnValue(new Promise(() => {}));

    renderWithProviders(<SettingsPage />);
    expect(screen.getByPlaceholderText("Enter API key")).toBeInTheDocument();
  });

  it("renders language selector buttons", () => {
    vi.mocked(systemApi.status).mockReturnValue(new Promise(() => {}));

    renderWithProviders(<SettingsPage />);
    expect(screen.getByText("English")).toBeInTheDocument();
    // Use a function matcher for the Chinese text
    expect(screen.getByText("繁體中文")).toBeInTheDocument();
  });

  it("renders save button", () => {
    vi.mocked(systemApi.status).mockReturnValue(new Promise(() => {}));

    renderWithProviders(<SettingsPage />);
    expect(screen.getByText("Save")).toBeInTheDocument();
  });

  it("shows system status cards when loaded", async () => {
    vi.mocked(systemApi.status).mockResolvedValue(mockStatus);

    renderWithProviders(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("System Status")).toBeInTheDocument();
    });
    expect(screen.getByText("Mode")).toBeInTheDocument();
    expect(screen.getByText("paper")).toBeInTheDocument();
    expect(screen.getByText("Uptime")).toBeInTheDocument();
    expect(screen.getByText("2h 0m")).toBeInTheDocument();
    expect(screen.getByText("Strategies Running")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Data Source")).toBeInTheDocument();
    expect(screen.getByText("yahoo")).toBeInTheDocument();
  });

  it("shows API key hint when not authenticated", () => {
    vi.mocked(systemApi.status).mockReturnValue(new Promise(() => {}));

    renderWithProviders(<SettingsPage />);
    expect(screen.getByText(/Please enter your API Key/)).toBeInTheDocument();
  });
});
