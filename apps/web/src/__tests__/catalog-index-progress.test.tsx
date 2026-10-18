import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CatalogIndexProgress } from "@/components/catalog-index-progress";

describe("catalog indexing progress", () => {
  it("shows an indeterminate queued state instead of an invented percentage", () => {
    render(<CatalogIndexProgress index={{ status: "queued", product_count: 48 }} />);
    expect(screen.getByText("Catalog queued for indexing")).toBeVisible();
    expect(screen.getByRole("progressbar")).not.toHaveAttribute("value");
    expect(screen.getByText("0 / 48 products verified")).toBeVisible();
  });

  it("uses verified product counts and does not claim readiness before job completion", () => {
    const view = render(<CatalogIndexProgress index={{ status: "running", product_count: 48, indexed_product_count: 12 }} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("value", "12");
    expect(screen.getByRole("progressbar")).toHaveAttribute("max", "48");
    view.rerender(<CatalogIndexProgress index={{ status: "running", product_count: 48, indexed_product_count: 48, serving_catalog_id: "previous" }} />);
    expect(screen.getByText("Indexing your catalog")).toBeVisible();
    expect(screen.getByText(/previous catalog remains available/)).toBeVisible();
    view.rerender(<CatalogIndexProgress index={{ status: "ready", product_count: 48, indexed_product_count: 48 }} />);
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("retains a failed job's observed counts without an animated progress bar", () => {
    render(<CatalogIndexProgress index={{ status: "failed", product_count: 48, indexed_product_count: 12, error_code: "INDEX_FAILED" }} />);
    expect(screen.getByText("Indexing needs attention")).toBeVisible();
    expect(screen.getByText("12 / 48 products verified")).toBeVisible();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });
});
