import { render, screen, fireEvent } from "@testing-library/react";
import { ErrorAlert } from "./ErrorAlert";

describe("ErrorAlert", () => {
  it("renders error message", () => {
    render(<ErrorAlert message="Something failed" />);
    expect(screen.getByText("Something failed")).toBeInTheDocument();
  });

  it("renders retry button when onRetry provided", () => {
    const onRetry = vi.fn();
    render(<ErrorAlert message="Error" onRetry={onRetry} />);
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("calls onRetry when retry button clicked", () => {
    const onRetry = vi.fn();
    render(<ErrorAlert message="Error" onRetry={onRetry} />);
    fireEvent.click(screen.getByText("Retry"));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("does not render retry button without onRetry", () => {
    render(<ErrorAlert message="Error" />);
    expect(screen.queryByText("Retry")).not.toBeInTheDocument();
  });
});
