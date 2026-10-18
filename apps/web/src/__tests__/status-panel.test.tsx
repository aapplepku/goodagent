import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusPanel } from "@/components/status-panel";

describe("StatusPanel", () => {
  it("renders ready dependency status", () => {
    render(
      <StatusPanel
        meta={{
          app_name: "Open Commerce Agent",
          version: "0.0.1",
          environment: "test",
          status: "ready",
          dependencies: [
            { name: "postgres", ok: true, latency_ms: 2.5, detail: null },
            { name: "redis", ok: true, latency_ms: 1.2, detail: null },
            { name: "qdrant", ok: true, latency_ms: 4.1, detail: null }
          ]
        }}
      />
    );

    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("GoodAgent")).toBeInTheDocument();
    expect(screen.queryByText("Open Commerce Agent")).not.toBeInTheDocument();
    expect(screen.getByText("postgres")).toBeInTheDocument();
    expect(screen.getAllByText("Online")).toHaveLength(3);
  });

  it("renders unavailable dependencies when metadata is missing", () => {
    render(<StatusPanel meta={null} />);

    expect(screen.getByText("GoodAgent API")).toBeInTheDocument();
    expect(screen.getByText("api unavailable")).toBeInTheDocument();
    expect(screen.getAllByText("Offline")).toHaveLength(3);
  });

  it("preserves a custom runtime name and the underlying API metadata", () => {
    const meta = {
      app_name: "Open Commerce Lab",
      version: "0.0.1",
      environment: "test",
      status: "ready" as const,
      dependencies: [],
    };
    const { rerender } = render(<StatusPanel meta={meta} />);
    expect(screen.getByText("Open Commerce Lab")).toBeInTheDocument();
    const defaultMeta = { ...meta, app_name: "Open Commerce Agent" };
    rerender(<StatusPanel meta={defaultMeta} />);
    expect(screen.getByText("GoodAgent")).toBeInTheDocument();
    expect(defaultMeta.app_name).toBe("Open Commerce Agent");
  });
});
