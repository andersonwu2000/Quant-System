import { screen } from "@testing-library/react";
import { renderWithProviders } from "@test/helpers";
import { NotFoundPage } from "./NotFoundPage";

describe("NotFoundPage", () => {
  it("renders 404 text", () => {
    renderWithProviders(<NotFoundPage />);
    expect(screen.getByText("404")).toBeInTheDocument();
  });

  it("shows page not found message", () => {
    renderWithProviders(<NotFoundPage />);
    expect(screen.getByText("Page not found")).toBeInTheDocument();
  });

  it("has a link back to dashboard", () => {
    renderWithProviders(<NotFoundPage />);
    const link = screen.getByText("Back to Dashboard");
    expect(link).toBeInTheDocument();
    expect(link.closest("a")).toHaveAttribute("href", "/");
  });
});
