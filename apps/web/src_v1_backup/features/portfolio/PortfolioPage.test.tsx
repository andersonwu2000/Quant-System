import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@test/helpers";
import { PortfolioPage } from "./PortfolioPage";
import type { Portfolio } from "@core/api";
import { portfolioApi } from "./api";

vi.mock("./api", () => ({
  portfolioApi: {
    get: vi.fn(),
  },
}));

const mockPortfolio: Portfolio = {
  nav: 1_000_000,
  cash: 150_000,
  gross_exposure: 0.85,
  net_exposure: 0.6,
  positions_count: 3,
  daily_pnl: -5_000,
  daily_pnl_pct: -0.005,
  positions: [
    {
      symbol: "AAPL",
      quantity: 200,
      avg_cost: 150.0,
      market_price: 175.5,
      market_value: 35_100,
      unrealized_pnl: 5_100,
      weight: 0.035,
    },
    {
      symbol: "TSLA",
      quantity: 50,
      avg_cost: 220.0,
      market_price: 210.0,
      market_value: 10_500,
      unrealized_pnl: -500,
      weight: 0.011,
    },
  ],
  as_of: "2024-01-15T10:00:00Z",
};

const emptyPortfolio: Portfolio = {
  nav: 1_000_000,
  cash: 1_000_000,
  gross_exposure: 0,
  net_exposure: 0,
  positions_count: 0,
  daily_pnl: 0,
  daily_pnl_pct: 0,
  positions: [],
  as_of: "2024-01-15T10:00:00Z",
};

describe("PortfolioPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("shows loading skeleton initially", () => {
    vi.mocked(portfolioApi.get).mockReturnValue(new Promise(() => {}));

    const { container } = renderWithProviders(<PortfolioPage />);
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("renders portfolio data after loading", async () => {
    vi.mocked(portfolioApi.get).mockResolvedValue(mockPortfolio);

    renderWithProviders(<PortfolioPage />);

    await waitFor(() => {
      expect(screen.getByText("Portfolio")).toBeInTheDocument();
    });

    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("TSLA")).toBeInTheDocument();
  });

  it("shows empty positions message when no positions", async () => {
    vi.mocked(portfolioApi.get).mockResolvedValue(emptyPortfolio);

    renderWithProviders(<PortfolioPage />);

    await waitFor(() => {
      expect(screen.getByText("No positions")).toBeInTheDocument();
    });
  });

  it("renders error state with retry", async () => {
    vi.mocked(portfolioApi.get).mockRejectedValue(new Error("Server error"));

    renderWithProviders(<PortfolioPage />);

    await waitFor(() => {
      expect(screen.getByText("Server error")).toBeInTheDocument();
    });
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("displays NAV and Cash metric labels", async () => {
    vi.mocked(portfolioApi.get).mockResolvedValue(mockPortfolio);

    renderWithProviders(<PortfolioPage />);

    await waitFor(() => {
      expect(screen.getByText("NAV")).toBeInTheDocument();
    });
    expect(screen.getByText("Cash")).toBeInTheDocument();
    expect(screen.getByText("Gross Exposure")).toBeInTheDocument();
    expect(screen.getByText("Net Exposure")).toBeInTheDocument();
    expect(screen.getByText("Daily P&L")).toBeInTheDocument();
  });
});
