import { render } from "@testing-library/react";
import { Skeleton, MetricCardSkeleton, TableSkeleton } from "./Skeleton";

describe("Skeleton", () => {
  it("renders with pulse animation", () => {
    const { container } = render(<Skeleton />);
    expect(container.firstChild).toHaveClass("animate-pulse");
  });

  it("applies custom className", () => {
    const { container } = render(<Skeleton className="h-4 w-20" />);
    expect(container.firstChild).toHaveClass("h-4", "w-20");
  });
});

describe("MetricCardSkeleton", () => {
  it("renders card structure", () => {
    const { container } = render(<MetricCardSkeleton />);
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });
});

describe("TableSkeleton", () => {
  it("renders correct number of rows", () => {
    const { container } = render(<TableSkeleton rows={3} cols={2} />);
    // header row + 3 data rows = 4 flex containers with gap-4
    const rows = container.querySelectorAll(".flex.gap-4");
    expect(rows).toHaveLength(4); // 1 header + 3 body
  });
});
