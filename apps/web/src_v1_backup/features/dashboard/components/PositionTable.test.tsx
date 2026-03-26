import { screen, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "@test/helpers";
import { PositionTable } from "./PositionTable";
import type { Position } from "@core/api";

function makePosition(overrides: Partial<Position> & { symbol: string }): Position {
  return {
    quantity: 100,
    avg_cost: 150,
    market_price: 160,
    market_value: 16000,
    unrealized_pnl: 1000,
    weight: 0.1,
    ...overrides,
  };
}

describe("PositionTable", () => {
  it("renders position rows", () => {
    const positions = [
      makePosition({ symbol: "AAPL" }),
      makePosition({ symbol: "MSFT", unrealized_pnl: -500 }),
    ];

    renderWithProviders(<PositionTable positions={positions} />);

    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("MSFT")).toBeInTheDocument();
    expect(screen.getByText("Top Positions")).toBeInTheDocument();
  });

  it("shows dash for null market_price", () => {
    const positions = [makePosition({ symbol: "TEST", market_price: null as unknown as number })];

    renderWithProviders(<PositionTable positions={positions} />);

    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("shows 'show all' button when more than 10 positions", () => {
    const positions = Array.from({ length: 12 }, (_, i) =>
      makePosition({ symbol: `SYM${i}` }),
    );

    renderWithProviders(<PositionTable positions={positions} />);

    // Only 10 visible initially
    expect(screen.queryByText("SYM11")).not.toBeInTheDocument();
    expect(screen.getByText("Show all (12)")).toBeInTheDocument();
  });

  it("toggles show all / show less", () => {
    const positions = Array.from({ length: 12 }, (_, i) =>
      makePosition({ symbol: `SYM${i}` }),
    );

    renderWithProviders(<PositionTable positions={positions} />);

    fireEvent.click(screen.getByText("Show all (12)"));
    expect(screen.getByText("SYM11")).toBeInTheDocument();
    expect(screen.getByText("Show less")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Show less"));
    expect(screen.queryByText("SYM11")).not.toBeInTheDocument();
  });

  it("does not show toggle for 10 or fewer positions", () => {
    const positions = Array.from({ length: 5 }, (_, i) =>
      makePosition({ symbol: `SYM${i}` }),
    );

    renderWithProviders(<PositionTable positions={positions} />);

    expect(screen.queryByText(/show all/i)).not.toBeInTheDocument();
  });
});
