import { screen, waitFor, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "@test/helpers";
import { StrategiesPage } from "./StrategiesPage";
import type { StrategyInfo } from "@quant/shared";
import { strategiesApi } from "./api";

vi.mock("./api", () => ({
  strategiesApi: {
    list: vi.fn(),
    start: vi.fn(),
    stop: vi.fn(),
  },
}));

// Mock auth to have trader-level role so start/stop buttons are visible
vi.mock("@core/auth", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => ({
    role: "trader",
    hasRole: (min: string) => ["viewer", "researcher", "trader"].includes(min),
    setRole: () => {},
    clearRole: () => {},
  }),
}));

const mockStrategies: StrategyInfo[] = [
  { name: "momentum", status: "running", pnl: 15_000 },
  { name: "mean_reversion", status: "stopped", pnl: -2_000 },
];

describe("StrategiesPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("shows loading skeleton initially", () => {
    vi.mocked(strategiesApi.list).mockReturnValue(new Promise(() => {}));

    const { container } = renderWithProviders(<StrategiesPage />);
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("renders strategy cards after loading", async () => {
    vi.mocked(strategiesApi.list).mockResolvedValue(mockStrategies);

    renderWithProviders(<StrategiesPage />);

    await waitFor(() => {
      expect(screen.getByText("momentum")).toBeInTheDocument();
    });
    expect(screen.getByText("mean_reversion")).toBeInTheDocument();
  });

  it("shows start/stop buttons based on status", async () => {
    vi.mocked(strategiesApi.list).mockResolvedValue(mockStrategies);

    renderWithProviders(<StrategiesPage />);

    await waitFor(() => {
      expect(screen.getByText("Stop")).toBeInTheDocument();
    });
    expect(screen.getByText("Start")).toBeInTheDocument();
  });

  it("calls stop API when stop button clicked on running strategy", async () => {
    vi.mocked(strategiesApi.list).mockResolvedValue(mockStrategies);
    vi.mocked(strategiesApi.stop).mockResolvedValue({ message: "Strategy momentum stopped" });

    renderWithProviders(<StrategiesPage />);

    await waitFor(() => {
      expect(screen.getByText("Stop")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Stop"));

    await waitFor(() => {
      expect(strategiesApi.stop).toHaveBeenCalledWith("momentum");
    });
  });

  it("calls start API when start button clicked on stopped strategy", async () => {
    vi.mocked(strategiesApi.list).mockResolvedValue(mockStrategies);
    vi.mocked(strategiesApi.start).mockResolvedValue({ message: "Strategy mean_reversion started" });

    renderWithProviders(<StrategiesPage />);

    await waitFor(() => {
      expect(screen.getByText("Start")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Start"));

    await waitFor(() => {
      expect(strategiesApi.start).toHaveBeenCalledWith("mean_reversion");
    });
  });

  it("renders error state with retry", async () => {
    vi.mocked(strategiesApi.list).mockRejectedValue(new Error("Connection refused"));

    renderWithProviders(<StrategiesPage />);

    await waitFor(() => {
      expect(screen.getByText("Connection refused")).toBeInTheDocument();
    });
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("shows no strategies message when empty", async () => {
    vi.mocked(strategiesApi.list).mockResolvedValue([]);

    renderWithProviders(<StrategiesPage />);

    await waitFor(() => {
      expect(screen.getByText("No strategies configured")).toBeInTheDocument();
    });
  });
});
