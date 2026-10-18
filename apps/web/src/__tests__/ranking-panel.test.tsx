import type { RankingModel, RankingOverview } from "@open-commerce/sdk-typescript";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { RankingPanel } from "../components/ranking-panel";

const model: RankingModel = {
  id: "11111111-1111-4111-8111-111111111111", catalog_id: "catalog", dataset_id: "dataset",
  goal: "Increase purchases from search", target: "purchase", method: "logistic_regression",
  status: "ready", active: false, artifact_hash: `sha256:${"a".repeat(64)}`,
  metrics: { eligible_for_activation: true, heldout_log_loss: 0.24 }, error: null,
  created_at: "2026-09-09T00:00:00Z", updated_at: "2026-09-09T00:00:00Z",
};
function clientFor(candidate = model) {
  const overview: RankingOverview = { catalog_id: "catalog", dataset: null, models: [candidate] };
  return {
    rankingOverview: vi.fn(async () => overview),
    trainRanking: vi.fn(async () => candidate),
    approveRanking: vi.fn(async () => overview),
    previewRanking: vi.fn(),
  };
}

it("requires explicit confirmation of the exact candidate and retains errors", async () => {
  const client = clientFor();
  render(<RankingPanel client={client} />);
  fireEvent.click(await screen.findByRole("button", { name: "Review & apply" }));
  expect(client.approveRanking).not.toHaveBeenCalled();
  client.approveRanking.mockRejectedValueOnce(new Error("Catalog changed; review again"));
  fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Catalog changed");
  expect(client.approveRanking).toHaveBeenCalledWith({
    model_id: model.id, artifact_hash: model.artifact_hash, expected_active_id: null,
    confirm: "APPLY_LOCAL_RANKING",
  }, expect.any(String));
  fireEvent.click(screen.getByRole("button", { name: "Refresh models" }));
  await waitFor(() => expect(client.rankingOverview).toHaveBeenCalledTimes(2));
  expect(screen.getByRole("alert")).toHaveTextContent("Catalog changed");
});

it("blocks a candidate below the offline baseline and does not invent training data", async () => {
  render(<RankingPanel client={clientFor({ ...model, metrics: { eligible_for_activation: false } })} />);
  expect(await screen.findByRole("button", { name: "Review & apply" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Build candidate" })).toBeDisabled();
  expect(screen.getByText("Below the offline baseline. Activation blocked.")).toBeVisible();
});
