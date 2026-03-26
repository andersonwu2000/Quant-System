import { render, screen } from "@testing-library/react";
import { MetricCard } from "./MetricCard";

describe("MetricCard", () => {
  it("renders label and value", () => {
    render(<MetricCard label="NAV" value="$1.5M" />);
    expect(screen.getByText("NAV")).toBeInTheDocument();
    expect(screen.getByText("$1.5M")).toBeInTheDocument();
  });

  it("renders sub text when provided", () => {
    render(<MetricCard label="P&L" value="$100K" sub="+5.00%" />);
    expect(screen.getByText("+5.00%")).toBeInTheDocument();
  });

  it("does not render sub when not provided", () => {
    const { container } = render(<MetricCard label="Cash" value="$50K" />);
    const paragraphs = container.querySelectorAll("p");
    expect(paragraphs).toHaveLength(2); // label + value only
  });

  it("applies custom className", () => {
    const { container } = render(<MetricCard label="X" value="Y" className="text-red-400" />);
    expect(container.firstChild).toHaveClass("text-red-400");
  });
});
