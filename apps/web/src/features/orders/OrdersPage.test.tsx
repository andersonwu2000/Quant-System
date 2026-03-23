import { screen, waitFor, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "@test/helpers";
import { OrdersPage } from "./OrdersPage";
import type { OrderInfo } from "@quant/shared";
import { ordersApi } from "./api";

vi.mock("./api", () => ({
  ordersApi: {
    list: vi.fn(),
    create: vi.fn(),
  },
}));

vi.mock("@core/hooks", async () => {
  const actual = await vi.importActual("@core/hooks");
  return {
    ...actual,
    useWs: vi.fn(),
  };
});

const mockOrders: OrderInfo[] = [
  {
    id: "ord-001",
    symbol: "AAPL",
    side: "BUY",
    quantity: 100,
    price: 175.5,
    status: "filled",
    filled_qty: 100,
    filled_avg_price: 175.48,
    commission: 25.0,
    created_at: "2024-01-15T09:30:00Z",
    strategy_id: "momentum",
  },
  {
    id: "ord-002",
    symbol: "TSLA",
    side: "SELL",
    quantity: 50,
    price: null,
    status: "pending",
    filled_qty: 0,
    filled_avg_price: 0,
    commission: 0,
    created_at: "2024-01-15T10:00:00Z",
    strategy_id: "mean_reversion",
  },
];

describe("OrdersPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("shows loading skeleton initially", () => {
    vi.mocked(ordersApi.list).mockReturnValue(new Promise(() => {}));

    const { container } = renderWithProviders(<OrdersPage />);
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("renders order rows after loading", async () => {
    vi.mocked(ordersApi.list).mockResolvedValue(mockOrders);

    renderWithProviders(<OrdersPage />);

    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
    });
    expect(screen.getByText("TSLA")).toBeInTheDocument();
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("SELL")).toBeInTheDocument();
  });

  it("renders filter buttons", () => {
    vi.mocked(ordersApi.list).mockReturnValue(new Promise(() => {}));

    renderWithProviders(<OrdersPage />);

    expect(screen.getByText("All")).toBeInTheDocument();
    expect(screen.getByText("Filled")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText("Cancelled")).toBeInTheDocument();
    expect(screen.getByText("Rejected")).toBeInTheDocument();
  });

  it("calls API with filter when filter button clicked", async () => {
    vi.mocked(ordersApi.list).mockResolvedValue(mockOrders);

    renderWithProviders(<OrdersPage />);

    // Wait for initial load to complete
    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
    });

    // Click on the "Cancelled" filter button (unique — doesn't appear in table data)
    fireEvent.click(screen.getByText("Cancelled"));

    await waitFor(() => {
      expect(ordersApi.list).toHaveBeenCalledWith("cancelled");
    });
  });

  it("shows empty orders message when no orders", async () => {
    vi.mocked(ordersApi.list).mockResolvedValue([]);

    renderWithProviders(<OrdersPage />);

    await waitFor(() => {
      expect(screen.getByText("No orders found")).toBeInTheDocument();
    });
  });

  it("shows error state with retry", async () => {
    vi.mocked(ordersApi.list).mockRejectedValue(new Error("Failed to fetch orders"));

    renderWithProviders(<OrdersPage />);

    await waitFor(() => {
      expect(screen.getByText("Failed to fetch orders")).toBeInTheDocument();
    });
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });
});
