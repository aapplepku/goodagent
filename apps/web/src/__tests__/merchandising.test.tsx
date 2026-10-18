import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { KpiPanel, PdpPreview } from "@/components/demo-workspace";
import type { ProductSummary } from "@open-commerce/sdk-typescript";

const recommendations = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", () => ({
  createBrowserClient: () => ({ recommendations }),
  apiErrorMessage: () => "Recommendations unavailable",
}));
const products: ProductSummary[] = [
  {
    product_id: "charger",
    title: "Synthetic charger",
    brand: "Fixture",
    category: "electronics",
    price: { amount_minor: 1000, currency: "USD" },
    inventory_units: 50,
    stock_state: "normal",
    quality_score: "0.5",
    popularity_score: "0.5",
    tags: [],
    index_status: "indexed",
    source_updated_at: "2026-01-01T00:00:00Z",
    active_action_count: 0,
  },
];

describe("Merchandising observations", () => {
  beforeEach(() => {
    recommendations.mockReset();
  });
  it("uses scoped PDP responses and does not fabricate empty recommendations", async () => {
    recommendations.mockResolvedValue({
      policy_version: 3,
      policy_active: true,
      strategy: "complements",
      results: [],
      trace: { results: [] },
    });
    render(<PdpPreview goalId="goal" products={products} />);
    fireEvent.click(screen.getByRole("button", { name: "Inspect PDP" }));
    expect(await screen.findByText("Version 3")).toBeVisible();
    expect(screen.getByText("complements / Active")).toBeVisible();
    expect(screen.getByText("No eligible recommendations.")).toBeVisible();
    expect(recommendations).toHaveBeenCalledWith({
      goal_context_id: "goal",
      surface: "product_detail",
      anchor_product_ids: ["charger"],
      top_k: 4,
      debug: true,
    });
  });
  it("shows an unavailable response without claiming an empty successful panel", async () => {
    recommendations.mockRejectedValue(new Error("offline"));
    render(<PdpPreview goalId="goal" products={products} />);
    fireEvent.click(screen.getByRole("button", { name: "Inspect PDP" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Recommendations unavailable",
    );
    expect(
      screen.queryByText("No eligible recommendations."),
    ).not.toBeInTheDocument();
  });
  it("has no acquisition KPI or invented profit for an empty merchandising store", () => {
    render(
      <KpiPanel
        merchandising
        metrics={null}
        baseline={null}
        series={null}
        definitions={[]}
      />,
    );
    expect(screen.getByText("Profit / Incoming session")).toBeVisible();
    expect(screen.queryByText("CAC")).not.toBeInTheDocument();
    expect(screen.queryByText("New customers")).not.toBeInTheDocument();
    expect(screen.queryByText("$0.00")).not.toBeInTheDocument();
  });
});
