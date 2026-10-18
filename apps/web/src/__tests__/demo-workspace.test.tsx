import { fireEvent, render, screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import {
  ActionInspector,
  DemoWorkspace,
  GoalWizard,
  GoalOverview,
  KpiPanel,
  MiniBars,
  idempotencyKey,
  ScenarioCards,
  TraceTimeline,
  SearchResultRow,
} from "@/components/demo-workspace";
import type {
  ControllerActionRecord,
  ControllerTraceEvent,
  GoalProgressResponse,
  GoalDraftResponse,
  MetricDefinition,
  MetricsSeriesResponse,
  ScenarioSummary,
  RankedCandidate,
} from "@open-commerce/sdk-typescript";

const scenarios: ScenarioSummary[] = [
  {
    id: "acquisition_v1",
    version: "test",
    display_name: "Acquisition",
    description: "Acquire customers",
    default_seed: 42,
    product_count: 1000,
    categories: ["footwear"],
    capabilities: [],
    default_goal: {},
    default_policy: {},
  },
  {
    id: "excess_inventory_v1",
    version: "test",
    display_name: "Excess inventory",
    description: "Clear stock",
    default_seed: 42,
    product_count: 1000,
    categories: ["home"],
    capabilities: [],
    default_goal: {},
    default_policy: {},
  },
  {
    id: "search_conversion_v1",
    version: "test",
    display_name: "Search conversion",
    description: "Improve discovery",
    default_seed: 42,
    product_count: 1000,
    categories: ["outdoor"],
    capabilities: [],
    default_goal: {},
    default_policy: {},
  },
];

describe("DemoWorkspace components", () => {
  it("renders the GoodAgent display name in the local demo", () => {
    const markup = renderToStaticMarkup(<DemoWorkspace initialMeta={null} />);
    expect(markup).toContain('aria-label="GoodAgent local demo"');
    expect(markup).toContain("<h1>GoodAgent</h1>");
  });

  it.each([
    [{ in_stock: true, price: true }, "2 passed"],
    [{ in_stock: false, price: true }, "FAIL: in_stock"],
    [{}, "Not recorded"],
  ])(
    "shows recorded relevance and filter evidence without assuming a pass",
    (constraintMatches, result) => {
      const candidate: RankedCandidate = {
        product_id: "product",
        title: "Synthetic trail shoe",
        brand: "Synthetic",
        category_path: ["footwear"],
        price: { amount_minor: 1234, currency: "USD" },
        highlights: [],
        score: "0.8",
        branch_ranks: { sparse: 1, dense: 2 },
        constraint_matches: constraintMatches,
        score_components: {
          relevance: "0.7",
          sparse: "0.6",
          dense: "0.5",
          rrf: "0.03",
          goal_boost: "0.1",
          final: "0.8",
        },
      };
      render(<SearchResultRow candidate={candidate} />);
      expect(
        screen.getByText(`Hard filters: ${result}`, { exact: false }),
      ).toBeVisible();
      expect(
        screen.getByText("Relevance 0.7 / Goal boost 0.1", { exact: false }),
      ).toBeVisible();
      expect(screen.getByText("$12.34")).toBeVisible();
    },
  );
  it.each([
    ["units_sold", "Units sold (whole store)", "count", "15", "15"],
    [
      "search_attributed_purchases",
      "Search-attributed purchases",
      "count",
      "7",
      "7",
    ],
    ["cac", "Customer acquisition cost", "minor_money", "1234", "$12.34"],
    [
      "contribution_profit",
      "Contribution profit",
      "minor_money",
      "-1234",
      "-$12.34",
    ],
    ["conversion_rate", "Conversion rate", "rate", "0.1234", "12.34%"],
    ["cac", "Customer acquisition cost", "minor_money", null, "unavailable"],
    ["cac", "Customer acquisition cost", "minor_money", "0", "$0.00"],
  ] as const)(
    "labels %s observations %s with correct units and availability",
    (metric, label, unit, value, displayed) => {
      const definition: MetricDefinition = {
        name: metric,
        label,
        unit,
        description: "Stored simulator metric",
        version: "test",
        freshness: "fresh",
      };
      const series: MetricsSeriesResponse = {
        metric,
        definition_version: "test",
        timezone: "UTC",
        attribution_model: "simulator_v1",
        freshness: "fresh",
        completeness_warnings:
          value === null ? ["Missing CAC observation."] : [],
        items: [{ timestamp: "2026-01-01T00:00:00Z", value }],
        next_cursor: null,
      };
      render(<MiniBars series={series} definition={definition} />);
      expect(
        screen.getByLabelText(`${label} by day (UTC)`),
      ).toBeInTheDocument();
      const point = screen.getByRole("listitem", {
        name: `2026-01-01: ${label}: ${displayed}`,
      });
      expect(point).toHaveAttribute(
        "title",
        `2026-01-01: ${label}: ${displayed}`,
      );
      if (value === null) {
        expect(point).toHaveTextContent("n/a");
        expect(screen.getByText("Missing CAC observation.")).toBeVisible();
        expect(point.querySelector(".metric-bar")).toBeNull();
      } else {
        const bar = point.querySelector(".metric-bar");
        expect(bar).toHaveAttribute(
          "data-sign",
          Number(value) < 0 ? "negative" : "nonnegative",
        );
        expect(bar).toHaveStyle({
          height: Number(value) === 0 ? "0%" : "100%",
        });
      }
    },
  );

  it("renders an empty series as no observations, without fabricated bars", () => {
    render(<MiniBars series={null} />);
    expect(screen.getByText("No observations")).toBeVisible();
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });

  it("places negative and positive observations on opposite sides of zero", () => {
    const series: MetricsSeriesResponse = {
      metric: "contribution_profit",
      definition_version: "test",
      timezone: "UTC",
      attribution_model: "simulator_v1",
      freshness: "fresh",
      completeness_warnings: [],
      next_cursor: null,
      items: [
        { timestamp: "2026-01-01T00:00:00Z", value: "-100" },
        { timestamp: "2026-01-02T00:00:00Z", value: "300" },
      ],
    };
    render(<MiniBars series={series} />);
    const [negative, positive] = screen.getAllByRole("listitem");
    expect(negative.querySelector(".metric-bar")).toHaveStyle({
      bottom: "0%",
      height: "25%",
    });
    expect(positive.querySelector(".metric-bar")).toHaveStyle({
      bottom: "25%",
      height: "75%",
    });
    expect(negative.querySelector(".metric-zero")).toHaveStyle({
      bottom: "25%",
    });
  });

  it.each([
    ["cac", "150", "100", "at_risk"],
    ["cac", "50", "100", "achieved"],
    ["new_customers", "50", "100", "at_risk"],
    ["cac", "50", "0", "at_risk"],
    ["cac", null, null, "insufficient_data"],
  ] as const)(
    "shows authoritative %s measurements %s/%s without inferring attainment",
    (metric, current, target, trajectory) => {
      const progress: GoalProgressResponse = {
        goal_id: "goal-1",
        tenant_id: "tenant-1",
        latest_run_id: null,
        objective_metric: metric,
        current_value: current,
        target_value: target,
        status: "active",
        pending_approvals: 2,
        denied_actions: 3,
        executable_actions: 0,
        succeeded_actions: 1,
        assessment: {
          metric,
          scope: "store",
          current_value: current,
          target_value: target,
          trajectory,
          feasibility: "not_ruled_out",
          projected_value: null,
          physical_upper_bound: null,
          reason_codes: [],
        },
      };
      const { container } = render(
        <GoalWizard
          draftText=""
          setDraftText={vi.fn()}
          selectedScenario="acquisition_v1"
          goalDraft={null}
          goal={null}
          progress={progress}
          capabilities={null}
          onDraft={vi.fn()}
          onLaunch={vi.fn()}
          disabled={false}
        />,
      );
      expect(
        screen.getByText(
          `Measured: ${current ?? "Not measured"}. Target: ${target ?? "open"}.`,
        ),
      ).toBeInTheDocument();
      expect(
        screen.getByText(trajectory.replaceAll("_", " ")),
      ).toBeInTheDocument();
      expect(
        screen.getByText("2 approvals, 3 denied, 0 executable"),
      ).toBeInTheDocument();
      expect(container.querySelector(".progress-track")).toBeNull();
      expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    },
  );

  it("does not fabricate a timestamped event before a run exists", () => {
    const { container } = render(
      <TraceTimeline trace={[]} run={null} eventsText="" />,
    );
    expect(screen.getByText("No trace yet.")).toBeInTheDocument();
    expect(container.querySelector("time")).toBeNull();
    expect(screen.queryByText("build snapshot")).not.toBeInTheDocument();
  });
  it("renders scenario cards and launches the selected scenario", () => {
    const onLaunch = vi.fn();

    render(
      <ScenarioCards
        scenarios={scenarios}
        selectedScenario="acquisition_v1"
        onSelect={vi.fn()}
        onLaunch={onLaunch}
        disabled={false}
      />,
    );

    expect(screen.getByText("Improve contribution profit")).toBeInTheDocument();
    expect(screen.getByText("No discounts")).toBeInTheDocument();
    expect(screen.getByText("Search only")).toBeInTheDocument();
    expect(screen.queryByText(/Connect Shopify/)).not.toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "Run scenario" })[0]);

    expect(onLaunch).toHaveBeenCalledWith("acquisition_v1");
  });

  it("renders ordered trace cards with evidence details", () => {
    const trace: ControllerTraceEvent[] = [
      {
        id: "event-1",
        tenant_id: "tenant-1",
        run_id: "run-1",
        sequence: 1,
        node: "build_snapshot",
        occurred_at: "2026-09-01T09:00:00Z",
        message: "Built read-only simulator observation snapshot",
        details: { state_hash: "sha256:test" },
      },
      {
        id: "event-2",
        tenant_id: "tenant-1",
        run_id: "run-1",
        sequence: 2,
        node: "evaluate_policy",
        occurred_at: "2026-09-01T09:01:00Z",
        message: "Evaluated explicit policy rules",
        details: { count: 4 },
      },
    ];

    render(<TraceTimeline trace={trace} run={null} eventsText="id: 1" />);

    expect(screen.getByText("build snapshot")).toBeInTheDocument();
    expect(screen.getByText("evaluate policy")).toBeInTheDocument();
    expect(
      screen.getByText("Persisted event page: 5 bytes."),
    ).toBeInTheDocument();
  });

  it("renders approval controls and policy reasons for the selected action", () => {
    const action = actionRecord("awaiting_approval");

    render(
      <ActionInspector
        actions={[action]}
        selectedAction={action}
        setSelectedActionId={vi.fn()}
        onApprove={vi.fn()}
        onReject={vi.fn()}
        onExecute={vi.fn()}
        onRollback={vi.fn()}
        disabled={false}
      />,
    );

    expect(screen.getByText("RISK_TIER_REQUIRES_APPROVAL")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve hash" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Execute" })).toBeDisabled();
    expect(screen.getByText("Create a bounded discount.")).toBeVisible();
    expect(screen.getByText("Estimated effect / Not observed")).toBeVisible();
    expect(screen.getByText("new customers: 5 to 24")).toBeVisible();
    expect(screen.getByText("Simulator execution: Not recorded")).toBeVisible();
    expect(screen.getByText("Reconciliation: Not recorded")).toBeVisible();
    expect(screen.getByText("Measurement: Not scheduled")).toBeVisible();
    expect(screen.queryByText("Observed Outcome")).not.toBeInTheDocument();
  });

  it("keeps missing observations distinct from real zero values", () => {
    render(
      <KpiPanel
        metrics={null}
        baseline={null}
        series={null}
        definitions={[]}
      />,
    );
    expect(screen.queryByText("$0.00")).not.toBeInTheDocument();
    expect(screen.queryByText("0%")).not.toBeInTheDocument();
    expect(screen.getAllByText("Not measured")).toHaveLength(2);
  });

  it("shows an empty goal overview without inferred attainment", () => {
    render(
      <GoalOverview
        goal={null}
        progress={null}
        metrics={null}
        instance={null}
      />,
    );
    expect(screen.getByText("No active goal selected")).toBeVisible();
    expect(screen.queryByText("achieved")).not.toBeInTheDocument();
    expect(
      screen.getByRole("list", { name: "Controller cycle" }),
    ).toBeVisible();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("requires a parsed draft before activation", () => {
    render(
      <GoalWizard
        draftText="Acquire 9000 new customers"
        setDraftText={vi.fn()}
        selectedScenario="acquisition_v1"
        goalDraft={null}
        goal={null}
        progress={null}
        capabilities={null}
        onDraft={vi.fn()}
        onLaunch={vi.fn()}
        disabled={false}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Activate and run" }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "Draft" })).toBeEnabled();
    expect(
      screen.queryByText("Objective", { exact: true }),
    ).not.toBeInTheDocument();
  });

  it.each([
    ["clarification_required", 42, "sha256:review", false],
    ["unsupported", 42, "sha256:review", false],
    ["ready_for_review", 43, "sha256:review", false],
    ["ready_for_review", 42, null, false],
    ["ready_for_review", 42, "sha256:review", true],
  ] as const)(
    "gates %s draft seed %s on exact review",
    (status, seed, hash, enabled) => {
      const draft: GoalDraftResponse = {
        status,
        draft:
          status === "unsupported"
            ? null
            : { seed, review_hash: hash, target_value: "1234" },
        ambiguities:
          status === "clarification_required" ? ["Specify a horizon."] : [],
        unsupported_requests:
          status === "unsupported" ? ["Unsupported objective."] : [],
        warnings: [],
      };
      const chooseMode = vi.fn();
      render(
        <GoalWizard
          draftText="Review this goal"
          setDraftText={vi.fn()}
          selectedScenario="acquisition_v1"
          goalDraft={draft}
          seed={42}
          goal={null}
          progress={null}
          capabilities={null}
          onDraft={vi.fn()}
          onLaunch={vi.fn()}
          disabled={false}
          onPlanningMode={chooseMode}
        />,
      );
      const activate = screen.getByRole("button", { name: "Activate and run" });
      if (enabled) expect(activate).toBeEnabled();
      else expect(activate).toBeDisabled();
      if (status === "clarification_required")
        expect(screen.getByText("Specify a horizon.")).toBeVisible();
      if (status === "unsupported")
        expect(screen.getByText("Unsupported objective.")).toBeVisible();
      fireEvent.change(
        screen.getByRole("combobox", { name: "Planning mode" }),
        { target: { value: "model_backed" } },
      );
      expect(chooseMode).toHaveBeenCalledWith("model_backed");
    },
  );

  it.each([
    ["minor_money", "1234", "4000", "$12.34 / $40.00"],
    ["rate", "0.256", "0.3", "25.6% / 30%"],
  ] as const)(
    "formats overview objectives as %s without inferred attainment",
    (unit, current, target, expected) => {
      const definition: MetricDefinition = {
        name: "cac",
        label: "Objective observation",
        unit,
        description: "Observed value",
        version: "test",
        freshness: "fresh",
      };
      const progress: GoalProgressResponse = {
        goal_id: "goal",
        tenant_id: "tenant",
        status: "active",
        objective_metric: "cac",
        current_value: current,
        target_value: target,
        pending_approvals: 0,
        executable_actions: 0,
        denied_actions: 0,
        succeeded_actions: 0,
        latest_run_id: null,
      };
      render(
        <GoalOverview
          goal={null}
          progress={progress}
          metrics={null}
          instance={null}
          definitions={[definition]}
        />,
      );
      expect(screen.getByText(expected)).toBeVisible();
      expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    },
  );

  it("scopes write idempotency keys to the mutated resource", () => {
    const key = idempotencyKey("execute", "action-1", "sha256:test-action");

    expect(key).toContain("execute-action-1-sha256:test-action");
  });
});

function actionRecord(
  status: ControllerActionRecord["action"]["status"],
): ControllerActionRecord {
  return {
    action: {
      id: "action-1",
      tenant_id: "tenant-1",
      goal_id: "goal-1",
      run_id: "run-1",
      intent: {
        type: "create_discount",
        rationale: "Create a bounded discount.",
        opportunity_ids: [],
        requested_by: {
          type: "agent",
          id: "deterministic-controller",
          roles: ["system"],
        },
        source_run_id: "run-1",
        proposed_at: "2026-09-01T09:00:00Z",
        discount_kind: "percentage",
        value: "0.10",
        starts_at: "2026-09-01T09:00:00Z",
        ends_at: "2026-09-08T09:00:00Z",
        product_scope: { product_ids: ["product-1"] },
        customer_scope: { segment: "new_customers", new_customers_only: true },
      },
      target_provider: {
        provider_type: "simulator",
        integration_id: null,
        resource_type: "simulator_instance",
        resource_id: "instance-1",
      },
      preconditions: [],
      estimated_cost: { amount_minor: 12000, currency: "USD" },
      budget_reservations: [],
      risk: { tier: "r2_reversible_material", confidence: "0.8", reasons: [] },
      idempotency_key: "fixture-action-1",
      expires_at: "2026-09-02T09:00:00Z",
      normalized_parameters: {
        discount_kind: "percentage",
        value: "0.10",
      },
      expected_impact: {
        metric: "new_customers",
        method: "discount_elasticity_prior_v1",
        interval: { point: "14", lower: "5", upper: "24", level: "0.80" },
        assumptions: [],
      },
      rollback_plan: {
        available: true,
        summary: "Disable the created discount.",
      },
      status,
    },
    action_version_hash: "sha256:test-action",
    policy_decision: {
      outcome: "require_approval",
      reason_codes: ["RISK_TIER_REQUIRES_APPROVAL"],
      evaluated_rules: [],
      required_approver_roles: ["operator"],
      valid_until: "2026-09-01T10:00:00Z",
    },
    approval_request: null,
    approval: null,
    execution_result: null,
    reconciliation: null,
    measurement: null,
    audit: [],
    created_at: "2026-09-01T09:01:00Z",
    updated_at: "2026-09-01T09:01:00Z",
  };
}
