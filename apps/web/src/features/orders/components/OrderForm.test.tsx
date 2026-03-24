import { screen, fireEvent, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@test/helpers";
import { OrderForm } from "./OrderForm";

const mockToast = vi.fn();
vi.mock("@shared/ui", async () => {
  const actual = await vi.importActual<typeof import("@shared/ui")>("@shared/ui");
  return {
    ...actual,
    useToast: () => ({ toast: mockToast }),
  };
});

vi.mock("../api", () => ({
  ordersApi: {
    create: vi.fn(),
  },
}));

const { ordersApi } = await import("../api");

describe("OrderForm", () => {
  const onSubmitted = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders all form fields", () => {
    renderWithProviders(<OrderForm onSubmitted={onSubmitted} />);

    expect(screen.getByText("New Order")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("SELL")).toBeInTheDocument();
  });

  it("submit button is disabled when symbol is empty", () => {
    renderWithProviders(<OrderForm onSubmitted={onSubmitted} />);

    const submitBtn = screen.getByText("Submit");
    expect(submitBtn).toBeDisabled();
  });

  it("shows confirmation panel on valid submit", () => {
    renderWithProviders(<OrderForm onSubmitted={onSubmitted} />);

    fireEvent.change(screen.getByPlaceholderText("AAPL"), { target: { value: "MSFT" } });
    fireEvent.change(screen.getByRole("spinbutton", { name: /qty/i }), { target: { value: "50" } });

    const form = screen.getByLabelText("New order form");
    fireEvent.submit(form);

    expect(screen.getByText("Confirm Order")).toBeInTheDocument();
    expect(screen.getByText("MSFT")).toBeInTheDocument();
  });

  it("calls API and resets form on confirm", async () => {
    vi.mocked(ordersApi.create).mockResolvedValue({} as never);

    renderWithProviders(<OrderForm onSubmitted={onSubmitted} />);

    fireEvent.change(screen.getByPlaceholderText("AAPL"), { target: { value: "AAPL" } });
    fireEvent.change(screen.getByRole("spinbutton", { name: /qty/i }), { target: { value: "10" } });

    const form = screen.getByLabelText("New order form");
    fireEvent.submit(form);

    // Click Confirm
    fireEvent.click(screen.getByText("Confirm"));

    await waitFor(() => {
      expect(ordersApi.create).toHaveBeenCalledWith({
        symbol: "AAPL",
        side: "BUY",
        quantity: 10,
        price: null,
      });
    });

    expect(mockToast).toHaveBeenCalledWith("success", "Order submitted successfully");
    expect(onSubmitted).toHaveBeenCalled();
  });

  it("toggles side to SELL", () => {
    renderWithProviders(<OrderForm onSubmitted={onSubmitted} />);

    fireEvent.click(screen.getByText("SELL"));

    const sellBtn = screen.getByText("SELL");
    expect(sellBtn.getAttribute("aria-pressed")).toBe("true");
  });

  it("sends price as number when filled", async () => {
    vi.mocked(ordersApi.create).mockResolvedValue({} as never);

    renderWithProviders(<OrderForm onSubmitted={onSubmitted} />);

    fireEvent.change(screen.getByPlaceholderText("AAPL"), { target: { value: "TSLA" } });
    fireEvent.change(screen.getByRole("spinbutton", { name: /qty/i }), { target: { value: "5" } });
    fireEvent.change(screen.getByPlaceholderText("Market"), { target: { value: "150.50" } });

    const form = screen.getByLabelText("New order form");
    fireEvent.submit(form);
    fireEvent.click(screen.getByText("Confirm"));

    await waitFor(() => {
      expect(ordersApi.create).toHaveBeenCalledWith(
        expect.objectContaining({ price: 150.50 }),
      );
    });
  });

  it("shows error on API failure", async () => {
    vi.mocked(ordersApi.create).mockRejectedValue(new Error("Forbidden"));

    renderWithProviders(<OrderForm onSubmitted={onSubmitted} />);

    fireEvent.change(screen.getByPlaceholderText("AAPL"), { target: { value: "AAPL" } });
    fireEvent.change(screen.getByRole("spinbutton", { name: /qty/i }), { target: { value: "10" } });

    const form = screen.getByLabelText("New order form");
    fireEvent.submit(form);
    fireEvent.click(screen.getByText("Confirm"));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith("error", "Failed to submit order");
    });
  });

  it("cancel dismisses confirmation", () => {
    renderWithProviders(<OrderForm onSubmitted={onSubmitted} />);

    fireEvent.change(screen.getByPlaceholderText("AAPL"), { target: { value: "AAPL" } });
    fireEvent.change(screen.getByRole("spinbutton", { name: /qty/i }), { target: { value: "10" } });

    const form = screen.getByLabelText("New order form");
    fireEvent.submit(form);

    expect(screen.getByText("Confirm Order")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Cancel"));

    expect(screen.queryByText("Confirm Order")).not.toBeInTheDocument();
  });
});
