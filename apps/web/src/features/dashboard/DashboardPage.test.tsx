import { screen } from "@testing-library/react";
import { renderWithProviders } from "@test/helpers";
import { DashboardPage } from "./DashboardPage";
import type { Portfolio } from "@core/api";
import { useDashboard } from "./hooks/useDashboard";

// Mock the useDashboard hook since it combines multiple API calls + WS
vi.mock("./hooks/useDashboard", () => ({
  useDashboard: vi.fn(),
}));

// Mock MarketTicker to avoid WS initialization requirement
vi.mock("./components/MarketTicker", () => ({
  MarketTicker: () => null,
}));

// Mock recharts to avoid canvas issues in jsdom
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children: React.ReactNode }) => <div data-testid="line-chart">{children}</div>,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  CartesianGrid: () => null,
}));

const mockPortfolio: Portfolio = {
  nav: 1_500_000,
  cash: 200_000,
  gross_exposure: 0.87,
  net_exposure: 0.65,
  positions_count: 5,
  daily_pnl: 12_500,
  daily_pnl_pct: 0.0084,
  positions: [
    {
      symbol: "AAPL",
      quantity: 100,
      avg_cost: 150.0,
      market_price: 175.0,
      market_value: 17_500,
      unrealized_pnl: 2_500,
      weight: 0.12,
    },
  ],
  as_of: "2024-01-15T10:00:00Z",
};

describe("DashboardPage", () => {
  it("shows loading skeleton when data is not yet available", () => {
    vi.mocked(useDashboard).mockReturnValue({
      pf: null,
      error: null,
      refresh: vi.fn(),
      navHistory: [],
      running: 0,
      runningStrats: [],
      connected: true,
    });

    const { container } = renderWithProviders(<DashboardPage />);
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("renders metric cards with portfolio data", () => {
    vi.mocked(useDashboard).mockReturnValue({
      pf: mockPortfolio,
      error: null,
      refresh: vi.fn(),
      navHistory: [],
      running: 2,
      runningStrats: [{ name: "momentum", status: "running", pnl: 100 } as any, { name: "rsi", status: "running", pnl: 50 } as any],
      connected: true,
    });

    renderWithProviders(<DashboardPage />);

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("NAV")).toBeInTheDocument();
    expect(screen.getByText("Cash")).toBeInTheDocument();
    expect(screen.getByText("Daily P&L")).toBeInTheDocument();
    expect(screen.getByText("Positions")).toBeInTheDocument();
    expect(screen.getByText("2 strategies running")).toBeInTheDocument();
  });

  it("renders error state with retry button", () => {
    const refresh = vi.fn();
    vi.mocked(useDashboard).mockReturnValue({
      pf: null,
      error: "Network error",
      refresh,
      navHistory: [],
      running: 0,
      runningStrats: [],
      connected: true,
    });

    renderWithProviders(<DashboardPage />);
    expect(screen.getByText("Network error")).toBeInTheDocument();
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("renders position table when positions exist", () => {
    vi.mocked(useDashboard).mockReturnValue({
      pf: mockPortfolio,
      error: null,
      refresh: vi.fn(),
      navHistory: [],
      running: 0,
      runningStrats: [],
      connected: true,
    });

    renderWithProviders(<DashboardPage />);
    expect(screen.getByText("AAPL")).toBeInTheDocument();
  });

  it("shows positions count as string", () => {
    vi.mocked(useDashboard).mockReturnValue({
      pf: mockPortfolio,
      error: null,
      refresh: vi.fn(),
      navHistory: [],
      running: 0,
      runningStrats: [],
      connected: true,
    });

    renderWithProviders(<DashboardPage />);
    expect(screen.getByText("5")).toBeInTheDocument();
  });
});
