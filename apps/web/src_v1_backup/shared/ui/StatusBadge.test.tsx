import { render, screen } from "@testing-library/react";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it("renders status text", () => {
    render(<StatusBadge status="running" />);
    expect(screen.getByText("running")).toBeInTheDocument();
  });

  it("applies correct style for running", () => {
    render(<StatusBadge status="running" />);
    expect(screen.getByText("running")).toHaveClass("bg-emerald-500/20");
  });

  it("applies correct style for failed", () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByText("failed")).toHaveClass("bg-red-500/20");
  });

  it("applies default style for unknown status", () => {
    render(<StatusBadge status="unknown" />);
    expect(screen.getByText("unknown")).toHaveClass("bg-slate-500/20");
  });
});
