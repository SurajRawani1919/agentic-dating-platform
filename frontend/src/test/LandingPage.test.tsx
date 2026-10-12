import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { LandingPage } from "../pages/LandingPage";

describe("LandingPage", () => {
  it("renders brand and workflow stages", () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "PAIRWISE" })).toBeInTheDocument();
    expect(screen.getByText(/Five-stage workflow/i)).toBeInTheDocument();
    expect(screen.getByText(/Agent dating/i)).toBeInTheDocument();
  });
});
