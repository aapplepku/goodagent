"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { apiErrorMessage } from "@/lib/api";
import { useMerchantClient } from "@/lib/merchant-transport";
import type {
  ActionStatus,
  ActionType,
  AuditFeedEntry,
  BaselineComparisonResponse,
  CapabilitiesResponse,
  ControllerActionRecord,
  ControllerPolicyConfig,
  ControllerRunRecord,
  ControllerTraceEvent,
  GoalCreateRequest,
  GoalDraftResponse,
  GoalProgressResponse,
  GoalRecord,
  InventoryItem,
  MetricDefinition,
  MetricsSeriesResponse,
  MetricsSummaryResponse,
  MetaResponse,
  PolicyValidationResponse,
  ProductSummary,
  RankedCandidate,
  RankingMode,
  RecommendationResponse,
  ScenarioId,
  ScenarioSummary,
  SearchResponse,
  SimulatorStateResponse,
} from "@open-commerce/sdk-typescript";

type DemoWorkspaceProps = {
  initialMeta: MetaResponse | null;
};

type ScenarioCopy = {
  label: string;
  objective: string;
  constraint: string;
  prompt: string;
};

type BusyState = {
  label: string;
} | null;

const SCENARIO_COPY: Record<ScenarioId, ScenarioCopy> = {
  acquisition_v1: {
    label: "Merchandising",
    objective: "Improve contribution profit",
    constraint: "Fixed traffic, bounded prices, promotions and discovery",
    prompt:
      "Merchandising: maximize contribution profit in 14 days; max base price change 10%; max effective discount 15%; promotion cap $50; minimum unit margin 25%",
  },
  excess_inventory_v1: {
    label: "No discounts",
    objective: "Clear excess inventory safely",
    constraint: "No promotions or effective markdowns below reference",
    prompt:
      "Merchandising: clear 200 excess inventory units in 14 days; no discounts; minimum unit margin 25%",
  },
  search_conversion_v1: {
    label: "Search only",
    objective: "Increase search purchases",
    constraint: "Use relevance-safe boosts and preserve stock guardrails",
    prompt:
      "Merchandising: maximize search purchases in 14 days; search only; minimum relevance 55%",
  },
};

const FALLBACK_SCENARIOS: ScenarioSummary[] = [
  {
    id: "acquisition_v1",
    version: "local",
    display_name: "Acquisition",
    description: "Win new customers while staying inside CAC and margin rules.",
    default_seed: 42,
    product_count: 1000,
    categories: ["apparel", "footwear", "outdoor"],
    capabilities: [],
    default_goal: {},
    default_policy: {},
  },
  {
    id: "excess_inventory_v1",
    version: "local",
    display_name: "Excess inventory",
    description: "Reduce overstock without unsafe discounting.",
    default_seed: 42,
    product_count: 1000,
    categories: ["apparel", "home", "outdoor"],
    capabilities: [],
    default_goal: {},
    default_policy: {},
  },
  {
    id: "search_conversion_v1",
    version: "local",
    display_name: "Search conversion",
    description: "Tune internal discovery while preserving relevance.",
    default_seed: 42,
    product_count: 1000,
    categories: ["footwear", "electronics", "outdoor"],
    capabilities: [],
    default_goal: {},
    default_policy: {},
  },
];

export function DemoWorkspace({ initialMeta }: DemoWorkspaceProps) {
  const client = useMerchantClient();
  const [meta, setMeta] = useState<MetaResponse | null>(initialMeta);
  const [capabilities, setCapabilities] = useState<CapabilitiesResponse | null>(
    null,
  );
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [selectedScenario, setSelectedScenario] =
    useState<ScenarioId>("acquisition_v1");
  const [seed, setSeed] = useState(42);
  const [planningMode, setPlanningMode] = useState<
    "deterministic" | "model_backed"
  >("deterministic");
  const [busy, updateBusy] = useState<BusyState>(null);
  const [notice, setNotice] = useState("Ready for a local no-key run.");
  const [instance, setInstance] = useState<SimulatorStateResponse | null>(null);
  const [goal, setGoal] = useState<GoalRecord | null>(null);
  const [savedGoals, setSavedGoals] = useState<GoalRecord[]>([]);
  const viewEpoch = useRef(0);
  const refreshSequence = useRef(0);
  const draftRequest = useRef<{ signature: string; key: string } | null>(null);
  const pendingReset = useRef<string | null>(null);
  function setBusy(next: BusyState) {
    // Discard reads begun before a mutation, including in-flight background polls.
    if (next !== null) refreshSequence.current += 1;
    updateBusy(next);
  }
  const [progress, setProgress] = useState<GoalProgressResponse | null>(null);
  const [run, setRun] = useState<ControllerRunRecord | null>(null);
  const [trace, setTrace] = useState<ControllerTraceEvent[]>([]);
  const [eventsText, setEventsText] = useState("");
  const [actions, setActions] = useState<ControllerActionRecord[]>([]);
  const [selectedActionId, setSelectedActionId] = useState<string | null>(null);
  const [policy, setPolicy] = useState<ControllerPolicyConfig | null>(null);
  const [policyDraft, setPolicyDraft] = useState("0.15");
  const [policyActions, setPolicyActions] = useState<ActionType[]>([]);
  const [policyValidation, setPolicyValidation] =
    useState<PolicyValidationResponse | null>(null);
  const [killSwitch, setKillSwitch] = useState(false);
  const [metrics, setMetrics] = useState<MetricsSummaryResponse | null>(null);
  const [series, setSeries] = useState<MetricsSeriesResponse | null>(null);
  const [baseline, setBaseline] = useState<BaselineComparisonResponse | null>(
    null,
  );
  const [metricDefinitions, setMetricDefinitions] = useState<
    MetricDefinition[]
  >([]);
  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [audit, setAudit] = useState<AuditFeedEntry[]>([]);
  const [draftText, setDraftText] = useState(
    SCENARIO_COPY.acquisition_v1.prompt,
  );
  const [goalDraft, setGoalDraft] = useState<GoalDraftResponse | null>(null);
  const [searchQuery, setSearchQuery] = useState(
    "waterproof trail shoes under $150",
  );
  const [searchMode, setSearchMode] = useState<RankingMode>("hybrid");
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);

  const visibleScenarios =
    scenarios.length > 0 ? scenarios : FALLBACK_SCENARIOS;
  const selectedAction =
    actions.find((record) => record.action.id === selectedActionId) ??
    actions[0] ??
    null;

  useEffect(() => {
    void loadBootstrap();
  }, []);

  const refreshRef = useRef(refreshWorkspace);
  refreshRef.current = refreshWorkspace;
  useEffect(() => {
    if (!goal || busy) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        await refreshRef.current({ goalId: goal?.spec.id }, false);
      } catch (error) {
        if (!stopped)
          setNotice(`Connection interrupted. ${apiErrorMessage(error)}`);
      }
      if (!stopped) timer = setTimeout(() => void poll(), 2000);
    }
    timer = setTimeout(() => void poll(), 1000);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [goal?.spec.id, busy]);

  async function loadBootstrap() {
    setBusy({ label: "Checking local runtime" });
    try {
      const [
        nextMeta,
        nextCapabilities,
        scenarioPage,
        nextPolicy,
        nextKill,
        definitions,
        goalPage,
      ] = await Promise.all([
        client.meta(),
        client.capabilities(),
        client.simulatorScenarios(),
        client.policy(),
        client.killSwitch(),
        client.metricDefinitions(),
        client.goals({ limit: 200 }),
      ]);
      setMeta(nextMeta);
      setCapabilities(nextCapabilities);
      setScenarios(scenarioPage.items);
      setPolicy(nextPolicy);
      setPolicyDraft(nextPolicy.discount_max_percentage ?? "");
      setPolicyActions(nextPolicy.allowed_action_types ?? []);
      setKillSwitch(nextKill.enabled);
      setMetricDefinitions(definitions.items);
      setSavedGoals(goalPage.items);
      const fromUrl = new URL(window.location.href).searchParams.get("goal");
      const restored = fromUrl
        ? await client.goal(fromUrl)
        : goalPage.items.at(-1);
      if (restored) await openGoal(restored);
      setNotice("Local runtime is connected.");
    } catch (error) {
      setNotice(`API unavailable. ${apiErrorMessage(error)}`);
    } finally {
      setBusy(null);
    }
  }

  function selectGoal(nextGoal: GoalRecord) {
    pendingReset.current = null;
    viewEpoch.current += 1;
    setGoal(nextGoal);
    setGoalDraft(null);
    setSavedGoals((items) => [
      ...items.filter((item) => item.spec.id !== nextGoal.spec.id),
      nextGoal,
    ]);
    setSelectedScenario(nextGoal.scenario_id);
    setSeed(nextGoal.seed);
    setPlanningMode(nextGoal.planning_mode ?? "deterministic");
    setRun(null);
    setTrace([]);
    setActions([]);
    setEventsText("");
    setSelectedActionId(null);
    setSearchResult(null);
    setProgress(null);
    setInstance(null);
    setMetrics(null);
    setSeries(null);
    setBaseline(null);
    const url = new URL(window.location.href);
    url.searchParams.set("goal", nextGoal.spec.id);
    window.history.replaceState(window.history.state, "", url);
  }

  async function openGoal(nextGoal: GoalRecord) {
    selectGoal(nextGoal);
    await refreshWorkspace({
      goalId: nextGoal.spec.id,
      instanceId: nextGoal.simulator_instance_id,
    });
  }

  async function selectSavedGoal(goalId: string) {
    setBusy({ label: "Loading saved goal" });
    try {
      await openGoal(await client.goal(goalId));
      setNotice("Saved goal loaded.");
    } catch (error) {
      setNotice(apiErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }

  async function launchScenario(
    scenarioId: ScenarioId,
    reviewedDraft?: GoalCreateRequest,
  ) {
    setSelectedScenario(scenarioId);
    setBusy({ label: "Launching scenario" });
    try {
      if (!reviewedDraft) {
        pendingReset.current = null;
        setDraftText(SCENARIO_COPY[scenarioId].prompt);
        setGoalDraft(null);
        setNotice("Review a typed goal before starting this scenario.");
        document
          .getElementById("goal-config")
          ?.scrollIntoView({ behavior: "smooth" });
        return false;
      }
      const createdGoal = await client.createGoal(
        reviewedDraft,
        idempotencyKey("goal", scenarioId, seed),
      );
      const resetSource = pendingReset.current;
      selectGoal(createdGoal);
      if (resetSource) {
        await client.archiveGoal(
          resetSource,
          idempotencyKey("archive-for-reset", resetSource),
        );
        pendingReset.current = null;
      }
      const activatedGoal = await client.activateGoal(
        createdGoal.spec.id,
        idempotencyKey("activate", createdGoal.spec.id),
      );
      selectGoal(activatedGoal);
      await client.runGoal(
        activatedGoal.spec.id,
        { execute_bounded_auto: false },
        idempotencyKey("run", activatedGoal.spec.id, scenarioId),
      );
      await refreshWorkspace({
        goalId: activatedGoal.spec.id,
        instanceId: activatedGoal.simulator_instance_id,
      });
      setNotice("Planning queued.");
      return true;
    } catch (error) {
      setNotice(apiErrorMessage(error));
      return false;
    } finally {
      setBusy(null);
    }
  }

  async function draftNaturalGoal() {
    pendingReset.current = null;
    setGoalDraft(null);
    setBusy({ label: "Drafting goal" });
    try {
      const signature = JSON.stringify({ draftText, seed, planningMode });
      if (draftRequest.current?.signature !== signature)
        draftRequest.current = {
          signature,
          key: idempotencyKey("draft", seed),
        };
      const draft = await client.draftGoal(
        {
          text: draftText,
          seed,
          planning_mode: planningMode,
        },
        draftRequest.current.key,
      );
      setGoalDraft(draft);
      if (draft.draft?.scenario_id)
        setSelectedScenario(draft.draft.scenario_id);
      setNotice(
        draft.status === "ready_for_review"
          ? "Draft ready for review."
          : draft.status === "unsupported"
            ? "Requested goal is unsupported."
            : "Goal needs clarification.",
      );
    } catch (error) {
      setNotice(apiErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }

  function editGoalText(text: string) {
    pendingReset.current = null;
    setDraftText(text);
    setGoalDraft(null);
  }

  async function runController() {
    if (!goal) {
      setNotice("Launch a scenario first.");
      return;
    }
    setBusy({ label: "Running controller" });
    try {
      const nextRun = await client.runGoal(
        goal.spec.id,
        { execute_bounded_auto: false },
        idempotencyKey("manual-run", goal.spec.id, run?.id ?? "initial"),
      );
      setRun(nextRun);
      await refreshWorkspace({
        instanceId: goal.simulator_instance_id,
        goalId: goal.spec.id,
        runId: nextRun.id,
      });
      setNotice("Planning queued.");
    } catch (error) {
      setNotice(apiErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }

  async function toggleGoalPause() {
    if (!goal) return;
    setBusy({
      label: goal.spec.status === "active" ? "Pausing goal" : "Resuming goal",
    });
    try {
      if (goal.spec.status === "active") {
        await client.pauseGoal(
          goal.spec.id,
          idempotencyKey("pause", goal.spec.id),
        );
      } else {
        await client.activateGoal(
          goal.spec.id,
          idempotencyKey("resume", goal.spec.id),
        );
      }
      await refreshWorkspace(currentIds());
      setNotice(
        goal.spec.status === "active" ? "Goal paused." : "Goal resumed.",
      );
    } catch (error) {
      setNotice(apiErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }

  async function advanceOneDay() {
    if (!goal) {
      setNotice("Launch a scenario first.");
      return;
    }
    setBusy({ label: "Advancing virtual day" });
    try {
      const nextState = await client.advanceSimulator(
        goal.simulator_instance_id,
        { hours: 24 },
        `advance-${goal.simulator_instance_id}-${instance?.day ?? "unknown"}`,
      );
      setInstance(nextState);
      await refreshWorkspace({
        instanceId: goal.simulator_instance_id,
        goalId: goal.spec.id,
      });
      setNotice("Virtual store advanced by one day.");
    } catch (error) {
      setNotice(apiErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }

  async function resetScenario() {
    if (!goal) {
      setNotice("Launch a scenario first.");
      return;
    }
    setBusy({ label: "Resetting scenario" });
    try {
      if (goal.planning_mode === "model_backed") {
        setGoalDraft(
          await client.reviewGoalConfiguration(resetGoalPayload(goal, seed)),
        );
        pendingReset.current = ["archived", "completed"].includes(
          goal.spec.status,
        )
          ? null
          : goal.spec.id;
        setNotice(
          "Review the fresh model-backed goal before activation. Current history is unchanged.",
        );
        return;
      }
      if (!["archived", "completed"].includes(goal.spec.status)) {
        await client.archiveGoal(
          goal.spec.id,
          idempotencyKey("archive-for-reset", goal.spec.id),
        );
      }
      if (
        await launchScenario(goal.scenario_id, resetGoalPayload(goal, seed))
      ) {
        setNotice("Fresh seeded goal created; previous history retained.");
      }
    } catch (error) {
      setNotice(apiErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }

  async function applyReviewedRevision() {
    if (
      !goal ||
      goalDraft?.status !== "ready_for_review" ||
      !goalDraft.draft?.review_hash
    )
      return;
    setBusy({ label: "Applying reviewed goal revision" });
    try {
      const revised = await client.updateGoal(
        goal.spec.id,
        {
          expected_revision: goal.revision ?? 1,
          replacement: goalDraft.draft,
        },
        idempotencyKey("revise", goal.spec.id, goal.revision),
      );
      selectGoal(revised);
      const active = await client.activateGoal(
        revised.spec.id,
        idempotencyKey("activate-revision", revised.spec.id, revised.revision),
      );
      selectGoal(active);
      await client.runGoal(
        active.spec.id,
        { execute_bounded_auto: false },
        idempotencyKey("revision-run", active.spec.id, active.revision),
      );
      await refreshWorkspace({
        goalId: active.spec.id,
        instanceId: active.simulator_instance_id,
      });
      setNotice(
        "Reviewed revision activated; stale proposals and pending approvals invalidated.",
      );
    } catch (error) {
      setNotice(apiErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }

  async function toggleKillSwitch() {
    setBusy({
      label: killSwitch ? "Disabling kill switch" : "Enabling kill switch",
    });
    try {
      const response = killSwitch
        ? await client.disableKillSwitch(
            idempotencyKey("kill-off", policy?.policy_version ?? "unknown"),
          )
        : await client.enableKillSwitch(
            idempotencyKey("kill-on", policy?.policy_version ?? "unknown"),
          );
      setKillSwitch(response.enabled);
      setPolicy(await client.policy());
      setNotice(
        response.enabled
          ? "Kill switch enabled. Writes are blocked."
          : "Kill switch off.",
      );
    } catch (error) {
      setNotice(apiErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }

  async function approveSelectedAction() {
    if (!selectedAction) {
      setNotice("No action selected.");
      return;
    }
    setBusy({ label: "Recording approval" });
    try {
      await client.approveAction(
        selectedAction.action.id,
        {
          action_version_hash: selectedAction.action_version_hash,
          comment: "Approved in the local v0.1 demo.",
        },
        idempotencyKey(
          "approve",
          selectedAction.action.id,
          selectedAction.action_version_hash,
        ),
      );
      await refreshWorkspace(currentIds());
      setNotice("Approval recorded. Execution queued.");
    } catch (error) {
      setNotice(apiErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }

  async function rejectSelectedAction() {
    if (!selectedAction) {
      setNotice("No action selected.");
      return;
    }
    setBusy({ label: "Recording rejection" });
    try {
      await client.rejectAction(
        selectedAction.action.id,
        {
          action_version_hash: selectedAction.action_version_hash,
          comment: "Rejected in the local v0.1 demo.",
        },
        idempotencyKey(
          "reject",
          selectedAction.action.id,
          selectedAction.action_version_hash,
        ),
      );
      await refreshWorkspace(currentIds());
      setNotice("Action rejected and audit trail updated.");
    } catch (error) {
      setNotice(apiErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }

  async function executeSelectedAction() {
    if (!selectedAction) {
      setNotice("No action selected.");
      return;
    }
    setBusy({ label: "Executing simulator action" });
    try {
      const result = await client.executeAction(
        selectedAction.action.id,
        idempotencyKey(
          "execute",
          selectedAction.action.id,
          selectedAction.action_version_hash,
        ),
      );
      await refreshWorkspace(currentIds());
      setNotice(
        result.action.status === "succeeded"
          ? "Simulator action executed and reconciled."
          : `Execution status: ${result.action.status ?? "unknown"}. Review the action before retrying.`,
      );
    } catch (error) {
      setNotice(apiErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }

  async function rollbackSelectedAction() {
    if (!selectedAction) {
      setNotice("No action selected.");
      return;
    }
    setBusy({ label: "Rolling back action" });
    try {
      const result = await client.rollbackAction(
        selectedAction.action.id,
        idempotencyKey(
          "rollback",
          selectedAction.action.id,
          selectedAction.action_version_hash,
        ),
      );
      await refreshWorkspace(currentIds());
      setNotice(
        result.action.status === "rolled_back"
          ? "Rollback completed through the simulator executor."
          : `Rollback status: ${result.action.status ?? "unknown"}. Review the action before retrying.`,
      );
    } catch (error) {
      setNotice(apiErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }

  async function validatePolicyDraft() {
    setBusy({ label: "Validating policy" });
    try {
      const response = await client.validatePolicy({
        policy: {
          discount_max_percentage: policyDraft,
          allowed_action_types: policyActions,
        },
      });
      setPolicyValidation(response);
      setNotice(
        response.valid
          ? "Policy draft is valid."
          : "Policy draft has warnings.",
      );
    } catch (error) {
      setNotice(apiErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }

  async function savePolicyDraft() {
    setBusy({ label: "Saving policy" });
    try {
      const response = await client.updatePolicy(
        {
          discount_max_percentage: policyDraft,
          allowed_action_types: policyActions,
        },
        idempotencyKey(
          "policy",
          policy?.policy_version ?? "unknown",
          policyDraft,
        ),
      );
      setPolicy(response);
      setPolicyValidation(null);
      setNotice("Policy version updated.");
    } catch (error) {
      setNotice(apiErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }

  async function runSearch() {
    setBusy({ label: "Searching catalog" });
    try {
      const response = await client.search({
        query: searchQuery,
        mode: searchMode,
        filters: { in_stock: true },
        top_k: 6,
        debug: true,
        goal_context_id: goal?.spec.id,
      });
      setSearchResult(response);
      setNotice("Search trace updated.");
    } catch (error) {
      setNotice(apiErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }

  async function refreshWorkspace(
    ids: {
      instanceId?: string | null;
      goalId?: string | null;
      runId?: string | null;
    },
    includeSnapshot = true,
  ) {
    const epoch = viewEpoch.current;
    const sequence = ++refreshSequence.current;
    const current = () =>
      epoch === viewEpoch.current && sequence === refreshSequence.current;
    const goalId = ids.goalId ?? goal?.spec.id ?? null;
    const [nextPolicy, nextKill, nextGoal, nextProgress, nextRuns] =
      await Promise.all([
        client.policy(),
        client.killSwitch(),
        goalId ? client.goal(goalId) : null,
        goalId ? client.goalProgress(goalId) : null,
        goalId ? client.runs(goalId) : null,
      ]);
    if (!current()) return;
    setPolicy(nextPolicy);
    if (includeSnapshot) {
      setPolicyDraft(nextPolicy.discount_max_percentage ?? "");
      setPolicyActions(nextPolicy.allowed_action_types ?? []);
    }
    setKillSwitch(nextKill.enabled);
    if (nextGoal) {
      setGoal(nextGoal);
      setSavedGoals((items) =>
        items.map((item) =>
          item.spec.id === nextGoal.spec.id ? nextGoal : item,
        ),
      );
    }
    setProgress(nextProgress);
    const currentRun =
      nextRuns?.items.find((item) => item.id === ids.runId) ??
      nextRuns?.items.find((item) => item.id === nextProgress?.latest_run_id) ??
      nextRuns?.items.at(-1) ??
      null;
    setRun(currentRun);
    const instanceId =
      ids.instanceId ?? nextGoal?.simulator_instance_id ?? instance?.id ?? null;
    const observed = instanceId
      ? await client.simulatorInstance(instanceId)
      : null;
    if (!current()) return;
    const changedDay =
      observed?.id !== instance?.id || observed?.day !== instance?.day;
    setInstance(observed);

    if (instanceId && (includeSnapshot || changedDay)) {
      const [
        nextMetrics,
        nextSeries,
        nextBaseline,
        nextProducts,
        nextInventory,
      ] = await Promise.all([
        client.metricSummary(instanceId),
        client.metricSeries({
          instanceId,
          metric: nextGoal?.spec.objective.metric ?? "new_customers",
          limit: 30,
        }),
        observed?.merchandising
          ? null
          : client.compareSimulatorBaseline(instanceId),
        client.catalogProducts({ instanceId, limit: 8 }),
        client.catalogInventory({ instanceId, limit: 8 }),
      ]);
      if (!current()) return;
      setMetrics(nextMetrics);
      setSeries(nextSeries);
      setBaseline(nextBaseline);
      setProducts(nextProducts.items);
      setInventory(nextInventory.items);
    }

    if (currentRun) {
      const [nextTrace, nextActions, nextEvents, nextAudit] = await Promise.all(
        [
          client.runTrace(currentRun.id),
          client.actions({ runId: currentRun.id, limit: 20 }),
          client.runEvents(currentRun.id),
          client.audit({ limit: 20 }),
        ],
      );
      if (!current()) return;
      setTrace(nextTrace.items);
      setEventsText(nextEvents);
      setActions(nextActions.items);
      setAudit(nextAudit.items);
      const preferred =
        nextActions.items.find(
          (record) => record.action.id === selectedActionId,
        ) ??
        nextActions.items.find(
          (record) => record.action.status === "awaiting_approval",
        ) ??
        nextActions.items.find(
          (record) => record.action.status === "executable",
        ) ??
        nextActions.items[0] ??
        null;
      setSelectedActionId(preferred?.action.id ?? null);
    }
  }

  function currentIds() {
    return {
      instanceId: goal?.simulator_instance_id ?? instance?.id ?? null,
      goalId: goal?.spec.id ?? null,
      runId: run?.id ?? null,
    };
  }

  return (
    <section className="demo-shell" aria-label="GoodAgent local demo">
      <header className="product-header">
        <div>
          <p className="eyebrow">Experimental / Simulator-first v0.1</p>
          <h1>GoodAgent</h1>
          <p className="summary">
            Merchandising / Pricing / Promotions / Product discovery
          </p>
          <p className="detail" role="note">
            Local demo only. Demo identity is not production authentication.
            Keep this workspace private and use synthetic data.
          </p>
        </div>
        <StatusDock
          meta={meta}
          capabilities={capabilities}
          busy={busy}
          notice={notice}
        />
      </header>

      <nav className="workspace-nav" aria-label="Workspace views">
        <a href="#current-goal">Overview</a>
        <a href="#goal-config">Goal</a>
        <a href="#agent-trace">Agent trace</a>
        <a href="#action-details">Actions</a>
        <a href="#outcomes">Outcomes</a>
        <a href="#search">Search</a>
        <a href="#policy">Policy</a>
      </nav>
      <GoalOverview
        definitions={metricDefinitions}
        goal={goal}
        progress={progress}
        metrics={metrics}
        instance={instance}
      />

      <ScenarioCards
        scenarios={visibleScenarios}
        selectedScenario={selectedScenario}
        onSelect={(scenarioId) => {
          setSelectedScenario(scenarioId);
          editGoalText(SCENARIO_COPY[scenarioId].prompt);
        }}
        onLaunch={launchScenario}
        disabled={busy !== null}
      />

      <section className="control-band" aria-label="Simulator controls">
        <label className="field">
          <span>Saved goal</span>
          <select
            aria-label="Saved goal"
            value={goal?.spec.id ?? ""}
            disabled={busy !== null || savedGoals.length === 0}
            onChange={(event) => void selectSavedGoal(event.target.value)}
          >
            <option value="" disabled>
              No saved goal
            </option>
            {savedGoals.map((item) => (
              <option key={item.spec.id} value={item.spec.id}>
                {item.spec.name} / seed {item.seed} / {shortId(item.spec.id)}
              </option>
            ))}
          </select>
        </label>
        <label className="field compact-field">
          <span>Seed</span>
          <input
            value={seed}
            type="number"
            step={1}
            onChange={(event) => {
              const value = Number(event.target.value);
              if (Number.isSafeInteger(value)) {
                pendingReset.current = null;
                setSeed(value);
                setGoalDraft(null);
              }
            }}
            inputMode="numeric"
          />
        </label>
        <ControlButton
          onClick={advanceOneDay}
          disabled={
            busy !== null ||
            !goal ||
            !instance ||
            instance.day >=
              Math.ceil(
                (Date.parse(goal.spec.horizon.end_at) -
                  Date.parse(goal.spec.horizon.start_at)) /
                  86400000,
              )
          }
        >
          Advance one day
        </ControlButton>
        <ControlButton
          onClick={runController}
          disabled={
            busy !== null ||
            !goal ||
            goal.spec.status !== "active" ||
            killSwitch
          }
        >
          Run controller
        </ControlButton>
        <ControlButton
          onClick={resetScenario}
          disabled={busy !== null || !goal}
        >
          Reset seed
        </ControlButton>
        <ControlButton
          onClick={toggleGoalPause}
          disabled={
            busy !== null ||
            !goal ||
            !["active", "paused"].includes(goal.spec.status)
          }
        >
          {goal?.spec.status === "paused" ? "Resume goal" : "Pause goal"}
        </ControlButton>
        <ControlButton
          onClick={toggleKillSwitch}
          disabled={busy !== null}
          tone={killSwitch ? "danger" : "neutral"}
        >
          {killSwitch ? "Kill switch on" : "Kill switch off"}
        </ControlButton>
      </section>

      <section className="workspace-grid">
        <GoalWizard
          draftText={draftText}
          setDraftText={editGoalText}
          selectedScenario={selectedScenario}
          goalDraft={goalDraft}
          seed={seed}
          planningMode={planningMode}
          onPlanningMode={(mode) => {
            pendingReset.current = null;
            setPlanningMode(mode);
            setGoalDraft(null);
          }}
          goal={goal}
          progress={progress}
          capabilities={capabilities}
          onDraft={draftNaturalGoal}
          onRevise={applyReviewedRevision}
          onLaunch={() =>
            goalDraft?.status === "ready_for_review" &&
            goalDraft.draft &&
            void launchScenario(selectedScenario, goalDraft.draft)
          }
          disabled={busy !== null}
        />
        <TraceTimeline trace={trace} run={run} eventsText={eventsText} />
        <ActionInspector
          actions={actions}
          selectedAction={selectedAction}
          setSelectedActionId={setSelectedActionId}
          onApprove={approveSelectedAction}
          onReject={rejectSelectedAction}
          onExecute={executeSelectedAction}
          onRollback={rollbackSelectedAction}
          disabled={busy !== null}
        />
      </section>

      <section className="outcome-grid">
        <SimulatorStatePanel
          instance={instance}
          products={products}
          inventory={inventory}
        />
        <KpiPanel
          metrics={metrics}
          baseline={baseline}
          series={series}
          definitions={metricDefinitions}
          merchandising={Boolean(goal?.spec.merchandising)}
        />
        <SearchPlayground
          query={searchQuery}
          setQuery={setSearchQuery}
          mode={searchMode}
          setMode={setSearchMode}
          result={searchResult}
          onSearch={runSearch}
          disabled={busy !== null}
        />
        {goal?.spec.merchandising ? (
          <PdpPreview
            key={`${goal.spec.id}:${instance?.current_time}:${instance?.merchandising?.recommendation_policy_version}`}
            goalId={goal.spec.id}
            products={products}
          />
        ) : null}
        <PolicyAuditPanel
          policy={policy}
          policyDraft={policyDraft}
          setPolicyDraft={setPolicyDraft}
          policyActions={policyActions}
          setPolicyActions={setPolicyActions}
          validation={policyValidation}
          audit={audit}
          killSwitch={killSwitch}
          onValidate={validatePolicyDraft}
          onSave={savePolicyDraft}
          disabled={busy !== null}
        />
      </section>
    </section>
  );
}

export function GoalOverview({
  goal,
  progress,
  metrics,
  instance,
  definitions = [],
}: {
  goal: GoalRecord | null;
  progress: GoalProgressResponse | null;
  metrics: MetricsSummaryResponse | null;
  instance: SimulatorStateResponse | null;
  definitions?: MetricDefinition[];
}) {
  const budget = goal?.spec.budgets.find((item) => item.kind === "goal");
  const definition = definitions.find(
    (item) => item.name === progress?.objective_metric,
  );
  const objectiveValue = (value: string | null | undefined) =>
    value == null
      ? "Not measured"
      : formatSeriesValue(Number(value), definition?.unit);
  const constraint = (name: string) => {
    const item = goal?.spec.constraints.find((value) => value.metric === name);
    if (!item) return "Not configured";
    const value =
      typeof item.value === "object"
        ? formatMoney(item.value.amount_minor, item.value.currency)
        : name === "cac"
          ? formatMoney(Number(item.value))
          : formatRate(item.value);
    return `${item.operator === "lte" ? "<=" : item.operator === "gte" ? ">=" : item.operator} ${value}`;
  };
  return (
    <section
      id="current-goal"
      className="goal-overview"
      aria-label="Current goal"
    >
      <div className="surface-header">
        <div>
          <p className="eyebrow">Current goal</p>
          <h2>{goal?.spec.name ?? "No active goal selected"}</h2>
        </div>
        <span className="badge info">
          {goal?.spec.status ?? "Not started"}
          {instance ? ` / Day ${instance.day}` : ""}
        </span>
      </div>
      <div className="goal-metrics">
        <MetricTile
          label={
            definition?.label ??
            progress?.objective_metric.replaceAll("_", " ") ??
            "Progress"
          }
          value={
            progress
              ? `${objectiveValue(progress.current_value)} / ${progress.target_value == null ? "open" : objectiveValue(progress.target_value)}`
              : "Not measured"
          }
        />
        <MetricTile
          label={
            goal?.spec.merchandising
              ? "Profit per eligible session"
              : "Current CAC"
          }
          value={
            goal?.spec.merchandising
              ? metrics?.totals.sessions
                ? formatMoney(
                    Math.round(
                      metrics.totals.contribution_profit_minor /
                        metrics.totals.sessions,
                    ),
                  )
                : "Not measured"
              : formatOptionalMoney(metrics?.totals.cac_minor)
          }
        />
        <MetricTile
          label="Contribution margin"
          value={formatRate(
            metrics?.totals.days
              ? metrics.totals.contribution_margin_rate
              : undefined,
          )}
        />
        <MetricTile
          label={
            goal?.spec.merchandising
              ? "Redeemed promotion value / Cap"
              : "Observed ad spend / Goal budget"
          }
          value={
            goal?.spec.merchandising
              ? `${formatOptionalMoney(instance?.merchandising?.promotion_redeemed_value_minor)} / ${formatMoney(goal.spec.merchandising.promotion_cap_minor ?? 0)}`
              : `${formatOptionalMoney(metrics?.totals.ad_spend_minor)} / ${budget ? formatMoney(budget.amount.amount_minor) : "Not set"}`
          }
        />
      </div>
      {goal ? (
        <div className="goal-constraints">
          {goal.spec.merchandising ? (
            <>
              <span>
                Unit margin &gt;={" "}
                {formatRate(goal.spec.merchandising.minimum_unit_margin)}
              </span>
              <span>
                Effective discount &lt;={" "}
                {formatRate(goal.spec.merchandising.max_effective_discount)}
              </span>
              <span>Advertising prohibited</span>
            </>
          ) : (
            <>
              <span>CAC {constraint("cac")}</span>
              <span>Margin {constraint("contribution_margin_rate")}</span>
              <span>Discount {constraint("discount_rate")}</span>
            </>
          )}
          <span>
            Autonomy:{" "}
            {goal.spec.autonomy.default_mode?.replaceAll("_", " ") ??
              "Not recorded"}
          </span>
          <span>
            Assessment:{" "}
            {progress?.assessment?.trajectory.replaceAll("_", " ") ??
              "Not assessed"}
          </span>
        </div>
      ) : null}
      <ol className="agent-loop" aria-label="Controller cycle">
        {[
          "Observe",
          "Diagnose",
          "Plan",
          "Estimate",
          "Policy / budget",
          "Act",
          "Measure",
          "Replan",
        ].map((stage) => (
          <li key={stage}>{stage}</li>
        ))}
      </ol>
    </section>
  );
}

function traceStage(node: ControllerTraceEvent["node"]): string {
  const stages: Record<ControllerTraceEvent["node"], string> = {
    load_goal_and_policy: "Authoritative state",
    acquire_run_lock: "Concurrency gate",
    build_snapshot: "Observe",
    detect_opportunities: "Diagnose",
    generate_hypotheses: "Hypothesis / Deterministic planner",
    generate_action_intents: "Plan / Typed proposals",
    compile_actions: "Compile / Validation",
    estimate: "Estimate / Not observed",
    evaluate_policy: "Policy / Deterministic enforcement",
    select_portfolio: "Budget / Portfolio selection",
    persist_proposals: "Durable proposals",
    approval_interrupt: "Approval / Human decision",
    execute_actions: "Act / Simulator executor",
    reconcile: "Reconcile / Provider state",
    schedule_measurement: "Measurement lifecycle / Inspect evidence",
    summarize: "Cycle status / Replan",
  };
  return stages[node];
}

export function ScenarioCards({
  scenarios,
  selectedScenario,
  onSelect,
  onLaunch,
  disabled,
}: {
  scenarios: ScenarioSummary[];
  selectedScenario: ScenarioId;
  onSelect: (scenarioId: ScenarioId) => void;
  onLaunch: (scenarioId: ScenarioId) => void;
  disabled: boolean;
}) {
  return (
    <section className="scenario-grid" aria-label="Demo scenarios">
      {scenarios.map((scenario) => {
        const copy = SCENARIO_COPY[scenario.id];
        const selected = scenario.id === selectedScenario;
        return (
          <article
            className={selected ? "scenario-card selected" : "scenario-card"}
            key={scenario.id}
          >
            <div>
              <p className="label">{copy.label}</p>
              <h2>{copy.objective}</h2>
              <p className="detail">{copy.constraint}</p>
            </div>
            <div className="scenario-meta">
              <span>48 synthetic products</span>
              <span>Seed {scenario.default_seed}</span>
            </div>
            <div className="scenario-actions">
              <button
                className="button secondary"
                type="button"
                onClick={() => onSelect(scenario.id)}
                disabled={disabled}
              >
                Review
              </button>
              <button
                className="button primary"
                type="button"
                onClick={() => onLaunch(scenario.id)}
                disabled={disabled}
              >
                Run scenario
              </button>
            </div>
          </article>
        );
      })}
    </section>
  );
}

export function TraceTimeline({
  trace,
  run,
  eventsText,
}: {
  trace: ControllerTraceEvent[];
  run: ControllerRunRecord | null;
  eventsText: string;
}) {
  return (
    <section
      className="surface timeline"
      id="agent-trace"
      aria-label="Run trace"
    >
      <div className="surface-header">
        <div>
          <h2>Observe, decide, act, measure</h2>
          <p className="detail">
            {run ? `Run ${shortId(run.id)} is ${run.status}` : "No run yet"}
          </p>
        </div>
        <span className="badge info">{trace.length} steps</span>
      </div>
      <p className="detail">
        {run?.summary?.planning_mode === "model_backed"
          ? "Planner: model-backed"
          : "Planner: deterministic / No LLM"}
      </p>
      {run?.summary?.planning_mode === "model_backed" ? (
        <>
          <p className="detail">
            Unverified model summary:{" "}
            {String(
              run.summary.model_decision_summary ??
                run.summary.model_error ??
                "Model work pending",
            )}
          </p>
          <details>
            <summary>Model evidence and usage</summary>
            <pre>
              {JSON.stringify(run.summary.model_planning ?? {}, null, 2)}
            </pre>
          </details>
        </>
      ) : null}
      {run?.next_run_at ? (
        <p className="detail">Next cycle: {formatTime(run.next_run_at)} UTC</p>
      ) : null}
      {run && run.opportunities && run.opportunities.length > 0 ? (
        <details className="diagnosis" open>
          <summary>Diagnosis and hypotheses</summary>
          {run.opportunities.map((item) => (
            <p key={item.id}>{item.description}</p>
          ))}
          {run.hypotheses?.map((item) => <p key={item.id}>{item.statement}</p>)}
        </details>
      ) : null}
      <div
        className="trace-list"
        tabIndex={0}
        aria-label="Persisted trace events"
      >
        {trace.length === 0 ? <p className="empty">No trace yet.</p> : null}
        {trace.map((event) => (
          <article className={`trace-card node-${event.node}`} key={event.id}>
            <time dateTime={event.occurred_at}>
              {formatTime(event.occurred_at)} UTC
            </time>
            <div>
              <span className="trace-stage">{traceStage(event.node)}</span>
              <p className="trace-node">{event.node.replaceAll("_", " ")}</p>
              <p>{event.message}</p>
              {Object.keys(event.details ?? {}).length > 0 ? (
                <details>
                  <summary>Evidence</summary>
                  <pre>{JSON.stringify(event.details, null, 2)}</pre>
                </details>
              ) : null}
            </div>
          </article>
        ))}
      </div>
      <details className="json-copy">
        <summary>Persisted trace JSON</summary>
        <pre>{JSON.stringify(trace, null, 2)}</pre>
      </details>
      {eventsText ? (
        <p className="detail">
          Persisted event page: {eventsText.length} bytes.
        </p>
      ) : null}
    </section>
  );
}

export function ActionInspector({
  actions,
  selectedAction,
  setSelectedActionId,
  onApprove,
  onReject,
  onExecute,
  onRollback,
  disabled,
}: {
  actions: ControllerActionRecord[];
  selectedAction: ControllerActionRecord | null;
  setSelectedActionId: (actionId: string) => void;
  onApprove: () => void;
  onReject: () => void;
  onExecute: () => void;
  onRollback: () => void;
  disabled: boolean;
}) {
  const params = asRecord(selectedAction?.action.normalized_parameters);
  const impact = asRecord(selectedAction?.action.expected_impact);
  const rollback = asRecord(selectedAction?.action.rollback_plan);

  return (
    <section
      className="surface action-panel"
      id="action-details"
      aria-label="Action details"
    >
      <div className="surface-header">
        <div>
          <h2>Actions and approvals</h2>
          <p className="detail">
            {actions.length} proposals in the current run
          </p>
        </div>
        <span className={statusBadge(selectedAction?.action.status)}>
          {selectedAction?.action.status ?? "none"}
        </span>
      </div>
      <div className="action-list">
        {actions.length === 0 ? (
          <p className="empty">Run a scenario to see proposals.</p>
        ) : null}
        {actions.map((record) => (
          <button
            className={
              record.action.id === selectedAction?.action.id
                ? "action-row selected"
                : "action-row"
            }
            type="button"
            key={record.action.id}
            onClick={() => setSelectedActionId(record.action.id)}
          >
            <span>{record.action.intent.type.replaceAll("_", " ")}</span>
            <span>
              {(record.action.status ?? "unknown").replaceAll("_", " ")}
            </span>
          </button>
        ))}
      </div>
      {selectedAction ? (
        <div className="action-detail">
          <section>
            <h3>Planner rationale</h3>
            <p>{selectedAction.action.intent.rationale}</p>
            <h3>What will change</h3>
            <dl className="facts">
              {Object.entries(params)
                .filter(([, value]) => typeof value !== "object")
                .map(([key, value]) => (
                  <div key={key}>
                    <dt>{key.replaceAll("_", " ")}</dt>
                    <dd>{String(value)}</dd>
                  </div>
                ))}
            </dl>
            <details>
              <summary>Typed parameters</summary>
              <pre>{JSON.stringify(params, null, 2)}</pre>
            </details>
          </section>
          <section>
            <h3>Estimated effect / Not observed</h3>
            <p>
              {stringValue(impact.metric).replaceAll("_", " ")}:{" "}
              {String(asRecord(impact.interval).lower ?? "n/a")} to{" "}
              {String(asRecord(impact.interval).upper ?? "n/a")}
            </p>
            <p>
              {stringValue(impact.method) || "Deterministic simulator estimate"}
            </p>
            <p className="detail">
              {impact.interval == null
                ? "Demand response: insufficient evidence"
                : "Uncalibrated heuristic interval"}
            </p>
            <details>
              <summary>Estimate assumptions</summary>
              <pre>{JSON.stringify(impact, null, 2)}</pre>
            </details>
          </section>
          <section>
            <h3>
              Proposal policy / Version {selectedAction.policy_version ?? 1}
            </h3>
            <p>{selectedAction.policy_decision.outcome.replaceAll("_", " ")}</p>
            <ul>
              {selectedAction.policy_decision.reason_codes.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
            <details>
              <summary>Deterministic rule checks</summary>
              {selectedAction.policy_decision.evaluated_rules.map((rule) => (
                <p key={rule.code}>
                  <strong>{rule.passed ? "PASS" : "FAIL"}</strong> / {rule.code}
                  : {rule.reason}
                </p>
              ))}
            </details>
          </section>
          <section>
            <h3>Approval and execution</h3>
            <p>
              Approval: {selectedAction.approval?.decision ?? "Not recorded"}
            </p>
            <p>
              Simulator execution:{" "}
              {selectedAction.execution_result?.status ?? "Not recorded"}
            </p>
            <p>
              Reconciliation:{" "}
              {selectedAction.reconciliation?.status ?? "Not recorded"}
            </p>
            <details>
              <summary>Exact action hash and receipts</summary>
              <pre>
                {JSON.stringify(
                  {
                    action_version_hash: selectedAction.action_version_hash,
                    approval: selectedAction.approval,
                    execution: selectedAction.execution_result,
                    reconciliation: selectedAction.reconciliation,
                  },
                  null,
                  2,
                )}
              </pre>
            </details>
          </section>
          <section>
            <h3>Rollback</h3>
            <p>{stringValue(rollback.summary) || "No rollback metadata"}</p>
            <details>
              <summary>Rollback metadata</summary>
              <pre>{JSON.stringify(rollback, null, 2)}</pre>
            </details>
          </section>
          {selectedAction.outcome ? (
            <section>
              <h3>Observed Outcome</h3>
              <p>
                {selectedAction.outcome.guardrail_status.replaceAll("_", " ")}
              </p>
              <p>{selectedAction.outcome.conclusion}</p>
              <details>
                <summary>Measurement</summary>
                <pre>
                  {JSON.stringify(
                    selectedAction.outcome.metric_results,
                    null,
                    2,
                  )}
                </pre>
              </details>
            </section>
          ) : (
            <p className="detail">
              Measurement:{" "}
              {selectedAction.measurement ? "Window pending" : "Not scheduled"}
            </p>
          )}
          <div className="action-buttons">
            <ControlButton
              onClick={onApprove}
              disabled={
                disabled || selectedAction.action.status !== "awaiting_approval"
              }
            >
              Approve hash
            </ControlButton>
            <ControlButton
              onClick={onReject}
              disabled={
                disabled || selectedAction.action.status !== "awaiting_approval"
              }
            >
              Reject
            </ControlButton>
            <ControlButton
              onClick={onExecute}
              disabled={
                disabled ||
                !["approved", "executable"].includes(
                  selectedAction.action.status ?? "unknown",
                )
              }
            >
              Execute
            </ControlButton>
            <ControlButton
              onClick={onRollback}
              disabled={
                disabled || selectedAction.action.status !== "succeeded"
              }
            >
              Roll back
            </ControlButton>
          </div>
        </div>
      ) : null}
    </section>
  );
}

export function GoalWizard({
  draftText,
  setDraftText,
  selectedScenario,
  goalDraft,
  seed = 42,
  planningMode = "deterministic",
  onPlanningMode,
  goal,
  progress,
  capabilities,
  onDraft,
  onLaunch,
  onRevise,
  disabled,
}: {
  draftText: string;
  setDraftText: (value: string) => void;
  selectedScenario: ScenarioId;
  goalDraft: GoalDraftResponse | null;
  seed?: number;
  planningMode?: "deterministic" | "model_backed";
  onPlanningMode?: (mode: "deterministic" | "model_backed") => void;
  goal: GoalRecord | null;
  progress: GoalProgressResponse | null;
  capabilities: CapabilitiesResponse | null;
  onDraft: () => void;
  onLaunch: () => void;
  onRevise?: () => void;
  disabled: boolean;
}) {
  return (
    <section
      className="surface wizard"
      id="goal-config"
      aria-label="Goal wizard"
    >
      <div className="surface-header">
        <div>
          <h2>Review goal configuration</h2>
          <p className="detail">
            {planningMode === "deterministic"
              ? "Deterministic"
              : "Model-backed"}{" "}
            / Review required
          </p>
        </div>
        <span className="badge info">
          {goalDraft ? goalDraft.status.replaceAll("_", " ") : "unparsed"}
        </span>
      </div>
      <label className="field">
        <span>Planning mode</span>
        <select
          value={planningMode}
          disabled={disabled}
          onChange={(event) =>
            onPlanningMode?.(
              event.target.value === "model_backed"
                ? "model_backed"
                : "deterministic",
            )
          }
        >
          <option value="deterministic">Deterministic</option>
          <option value="model_backed">Model-backed</option>
        </select>
      </label>
      <label className="field">
        <span>Natural-language draft</span>
        <textarea
          value={draftText}
          onChange={(event) => setDraftText(event.target.value)}
          rows={4}
          disabled={disabled}
        />
      </label>
      <div className="button-row">
        <ControlButton onClick={onDraft} disabled={disabled}>
          Draft
        </ControlButton>
        {goal && onRevise ? (
          <ControlButton
            onClick={onRevise}
            disabled={
              disabled ||
              goalDraft?.status !== "ready_for_review" ||
              !goalDraft.draft?.review_hash ||
              goalDraft.draft.seed !== goal.seed ||
              goalDraft.draft.scenario_id !== goal.scenario_id ||
              ["archived", "completed"].includes(goal.spec.status)
            }
          >
            Apply and activate revision {(goal.revision ?? 1) + 1}
          </ControlButton>
        ) : null}
        <ControlButton
          onClick={onLaunch}
          disabled={
            disabled ||
            goalDraft?.status !== "ready_for_review" ||
            !goalDraft.draft?.review_hash ||
            goalDraft.draft.seed !== seed
          }
          tone="primary"
        >
          Activate and run
        </ControlButton>
      </div>
      {progress ? (
        <div className="progress-block">
          <p className="label">
            {progress.objective_metric.replaceAll("_", " ")}
          </p>
          <p className="detail">
            Measured: {progress.current_value ?? "Not measured"}. Target:{" "}
            {progress.target_value ?? "open"}.
          </p>
          <p className="detail">
            {progress.pending_approvals} approvals, {progress.denied_actions}{" "}
            denied, {progress.executable_actions} executable
          </p>
          {progress.assessment ? (
            <p className="detail">
              {progress.assessment.feasibility === "infeasible"
                ? "Target exceeds available inventory."
                : progress.assessment.trajectory.replaceAll("_", " ")}
              {progress.assessment.projected_value !== null
                ? ` Recent-rate projection: ${Number(progress.assessment.projected_value).toFixed(1)} (uncalibrated).`
                : ""}
            </p>
          ) : null}
        </div>
      ) : null}
      <details>
        <summary>New goal review</summary>
        <pre>
          {JSON.stringify(
            goalDraft
              ? goalDraft.draft
              : { scenario: selectedScenario, status: "Draft not parsed" },
            null,
            2,
          )}
        </pre>
      </details>
      {goal ? (
        <details>
          <summary>Saved goal / Exact configuration</summary>
          <pre>{JSON.stringify(goal.spec, null, 2)}</pre>
        </details>
      ) : null}
      <ul className="warnings">
        {(goalDraft
          ? [
              ...(goalDraft.unsupported_requests ?? []),
              ...(goalDraft.ambiguities ?? []),
              ...(goalDraft.warnings ?? []),
            ]
          : (capabilities?.limitations ?? [])
        ).map((warning) => (
          <li key={warning}>{warning}</li>
        ))}
      </ul>
    </section>
  );
}

function SimulatorStatePanel({
  instance,
  products,
  inventory,
}: {
  instance: SimulatorStateResponse | null;
  products: ProductSummary[];
  inventory: InventoryItem[];
}) {
  return (
    <section className="surface state-panel" aria-label="Simulator state">
      <div className="surface-header">
        <div>
          <p className="label">Simulated store</p>
          <p className="detail">
            {instance
              ? `Day ${instance.day}, seed ${instance.seed}`
              : "No scenario running"}
          </p>
        </div>
        <span className="badge info">{instance?.status ?? "idle"}</span>
      </div>
      <div className="state-grid">
        <MetricTile
          label="Products"
          value={instance?.catalog.product_count ?? 0}
        />
        <MetricTile
          label="Inventory units"
          value={instance?.catalog.inventory_units ?? 0}
        />
        <MetricTile label="Discounts" value={instance?.active_discounts ?? 0} />
        <MetricTile
          label="Search boosts"
          value={instance?.active_search_boosts ?? 0}
        />
      </div>
      {instance?.merchandising ? (
        <>
          <h3>PDP recommendation policy</h3>
          <p>
            {instance.merchandising.recommendation_strategy} / Version{" "}
            {instance.merchandising.recommendation_policy_version}
          </p>
          <p>
            {instance.merchandising.serving_batches} serving batches /{" "}
            {instance.merchandising.recorded_checkouts} recorded checkouts
          </p>
        </>
      ) : (
        <>
          <h3>Campaigns</h3>
          <div className="compact-list">
            {(instance?.campaigns ?? []).slice(0, 4).map((campaign) => (
              <p key={campaign.id}>
                <span>{campaign.name}</span>
                <strong>{formatMoney(campaign.daily_budget_minor)}</strong>
              </p>
            ))}
          </div>
        </>
      )}
      <h3>Catalog signals</h3>
      <div className="compact-list">
        {products.slice(0, 4).map((product) => (
          <p key={product.product_id}>
            <span>{product.title}</span>
            <strong>{product.stock_state}</strong>
          </p>
        ))}
        {inventory.slice(0, 2).map((item) => (
          <p key={`inventory-${item.product_id}`}>
            <span>{item.category}</span>
            <strong>{item.inventory_units.toLocaleString()} units</strong>
          </p>
        ))}
      </div>
    </section>
  );
}

export function KpiPanel({
  metrics,
  baseline,
  series,
  definitions,
  merchandising = false,
}: {
  metrics: MetricsSummaryResponse | null;
  baseline: BaselineComparisonResponse | null;
  series: MetricsSeriesResponse | null;
  definitions: MetricDefinition[];
  merchandising?: boolean;
}) {
  const totals = metrics?.totals;
  return (
    <section className="surface kpi-panel" id="outcomes" aria-label="Outcomes">
      <div className="surface-header">
        <div>
          <p className="label">Outcomes</p>
          <p className="detail">
            {metrics?.freshness ?? "empty"} simulator data
          </p>
        </div>
        <span className="badge info">{totals?.days ?? 0} days</span>
      </div>
      <div className="state-grid">
        <MetricTile
          label={merchandising ? "Orders" : "New customers"}
          value={
            (merchandising ? totals?.orders : totals?.new_customers) ??
            "Not measured"
          }
        />
        <MetricTile
          label={merchandising ? "Profit / Incoming session" : "CAC"}
          value={formatOptionalMoney(
            merchandising
              ? totals?.sessions
                ? totals.contribution_profit_minor / totals.sessions
                : undefined
              : totals?.cac_minor,
          )}
        />
        <MetricTile
          label="Margin / Gross revenue"
          value={formatRate(
            totals?.days ? totals.contribution_margin_rate : undefined,
          )}
        />
        <MetricTile
          label="Profit"
          value={formatOptionalMoney(totals?.contribution_profit_minor)}
        />
      </div>
      <MiniBars
        series={series}
        definition={definitions.find(
          (definition) => definition.name === series?.metric,
        )}
      />
      <div className="baseline-row">
        <p>
          <span>Matched baseline delta (synthetic)</span>
          <strong>
            {baseline ? `${baseline.delta.new_customers} customers` : "not run"}
          </strong>
        </p>
        <p>
          <span>Observed ad spend</span>
          <strong>{formatOptionalMoney(totals?.ad_spend_minor)}</strong>
        </p>
      </div>
      <details>
        <summary>Metric definitions</summary>
        <ul>
          {definitions.slice(0, 5).map((definition) => (
            <li key={definition.name}>
              <strong>{definition.label}</strong>: {definition.description}
            </li>
          ))}
        </ul>
      </details>
    </section>
  );
}

export function PdpPreview({
  goalId,
  products,
}: {
  goalId: string;
  products: ProductSummary[];
}) {
  const client = useMerchantClient();
  const [anchor, setAnchor] = useState("");
  const [result, setResult] = useState<RecommendationResponse | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selected = anchor || products[0]?.product_id || "";

  async function inspect() {
    setPending(true);
    setResult(null);
    setError(null);
    try {
      setResult(
        await client.recommendations({
          goal_context_id: goalId,
          surface: "product_detail",
          anchor_product_ids: [selected],
          top_k: 4,
          debug: true,
        }),
      );
    } catch (cause) {
      setError(apiErrorMessage(cause));
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="surface" aria-label="Product detail recommendations">
      <div className="surface-header">
        <h2>Product detail recommendations</h2>
        <span className="badge info">
          {result ? `Version ${result.policy_version}` : "Not queried"}
        </span>
      </div>
      <label className="field">
        <span>PDP product</span>
        <select
          value={selected}
          disabled={pending}
          onChange={(event) => {
            setAnchor(event.target.value);
            setResult(null);
            setError(null);
          }}
        >
          {products.map((product) => (
            <option key={product.product_id} value={product.product_id}>
              {product.title}
            </option>
          ))}
        </select>
      </label>
      <ControlButton
        onClick={() => void inspect()}
        disabled={pending || !selected}
      >
        {pending ? "Loading PDP" : "Inspect PDP"}
      </ControlButton>
      {error ? <p role="alert">{error}</p> : null}
      {result ? (
        <>
          <p>
            {result.strategy} /{" "}
            {result.policy_active ? "Active" : "Default fallback"}
          </p>
          {result.results.length ? (
            result.results.map((candidate) => (
              <SearchResultRow
                key={candidate.product_id}
                candidate={candidate}
              />
            ))
          ) : (
            <p className="empty">No eligible recommendations.</p>
          )}
          <details>
            <summary>PDP serving evidence</summary>
            <pre>{JSON.stringify(result.trace, null, 2)}</pre>
          </details>
        </>
      ) : null}
    </section>
  );
}

function SearchPlayground({
  query,
  setQuery,
  mode,
  setMode,
  result,
  onSearch,
  disabled,
}: {
  query: string;
  setQuery: (value: string) => void;
  mode: RankingMode;
  setMode: (value: RankingMode) => void;
  result: SearchResponse | null;
  onSearch: () => void;
  disabled: boolean;
}) {
  const modes: RankingMode[] = [
    "sparse",
    "dense",
    "hybrid",
    "hybrid_reranked",
    "hybrid_boosted",
  ];
  return (
    <section
      className="surface search-panel"
      id="search"
      aria-label="Search playground"
    >
      <div className="surface-header">
        <div>
          <p className="label">Search playground</p>
          <p className="detail">{result?.ranking_version ?? "Not queried"}</p>
        </div>
        <span className="badge info">
          {result?.results.length ?? 0} results
        </span>
      </div>
      <p className="detail">Sparse + dense / Relevance gate / Bounded boost</p>
      <label className="field">
        <span>Query</span>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>
      <div className="segmented" role="radiogroup" aria-label="Ranking mode">
        {modes.map((item) => (
          <button
            className={item === mode ? "selected" : ""}
            key={item}
            type="button"
            role="radio"
            aria-checked={item === mode}
            onClick={() => setMode(item)}
          >
            {item.replace("_", "+")}
          </button>
        ))}
      </div>
      <ControlButton onClick={onSearch} disabled={disabled} tone="primary">
        Search
      </ControlButton>
      {result ? (
        <div className="search-results">
          <p className="detail">
            Parsed as {result.interpretation.normalized_query}; decision{" "}
            {result.evaluation.decision}.
          </p>
          {result.results.slice(0, 4).map((candidate) => (
            <SearchResultRow candidate={candidate} key={candidate.product_id} />
          ))}
          <details>
            <summary>Debug trace</summary>
            <pre tabIndex={0} aria-label="Complete search trace">
              {JSON.stringify(result.trace, null, 2)}
            </pre>
          </details>
        </div>
      ) : (
        <p className="empty">Search results will appear here.</p>
      )}
    </section>
  );
}

function PolicyAuditPanel({
  policy,
  policyDraft,
  setPolicyDraft,
  policyActions,
  setPolicyActions,
  validation,
  audit,
  killSwitch,
  onValidate,
  onSave,
  disabled,
}: {
  policy: ControllerPolicyConfig | null;
  policyDraft: string;
  setPolicyDraft: (value: string) => void;
  policyActions: ActionType[];
  setPolicyActions: (value: ActionType[]) => void;
  validation: PolicyValidationResponse | null;
  audit: AuditFeedEntry[];
  killSwitch: boolean;
  onValidate: () => void;
  onSave: () => void;
  disabled: boolean;
}) {
  return (
    <section
      className="surface policy-panel"
      id="policy"
      aria-label="Policy and audit"
    >
      <div className="surface-header">
        <div>
          <p className="label">Policy and audit</p>
          <p className="detail">Version {policy?.policy_version ?? 1}</p>
        </div>
        <span className={killSwitch ? "badge danger" : "badge ready"}>
          {killSwitch ? "Kill switch on" : "Kill switch off"}
        </span>
      </div>
      <label className="field">
        <span>Maximum discount</span>
        <input
          value={policyDraft}
          onChange={(event) => setPolicyDraft(event.target.value)}
        />
      </label>
      <fieldset>
        <legend>Allowed action families</legend>
        {(
          [
            "set_variant_price",
            "create_discount",
            "disable_discount",
            "set_search_boost",
            "set_recommendation_policy",
            "set_campaign_budget",
            "no_op",
          ] as ActionType[]
        ).map((action) => (
          <label key={action} style={{ display: "block" }}>
            <input
              type="checkbox"
              checked={policyActions.includes(action)}
              disabled={disabled}
              onChange={(event) =>
                setPolicyActions(
                  event.target.checked
                    ? [...policyActions, action]
                    : policyActions.filter((value) => value !== action),
                )
              }
            />
            {action.replaceAll("_", " ")}
          </label>
        ))}
      </fieldset>
      <div className="button-row">
        <ControlButton onClick={onValidate} disabled={disabled}>
          Validate
        </ControlButton>
        <ControlButton onClick={onSave} disabled={disabled} tone="primary">
          Save
        </ControlButton>
      </div>
      <p className="detail">
        {validation
          ? validation.valid
            ? "Dry run passed."
            : validation.reason_codes.join(", ")
          : "Dry-run results appear after validation."}
      </p>
      <details>
        <summary>Advanced YAML</summary>
        <pre>{policyYaml(policy)}</pre>
      </details>
      <h3>Audit</h3>
      <div className="compact-list">
        {audit.length === 0 ? (
          <p className="empty">No audit entries yet.</p>
        ) : null}
        {audit.slice(0, 5).map((entry) => (
          <p key={entry.id}>
            <span>{entry.event_type.replaceAll("_", " ")}</span>
            <strong>{entry.actor_role}</strong>
          </p>
        ))}
      </div>
    </section>
  );
}

function StatusDock({
  meta,
  capabilities,
  busy,
  notice,
}: {
  meta: MetaResponse | null;
  capabilities: CapabilitiesResponse | null;
  busy: BusyState;
  notice: string;
}) {
  const ready = meta?.status === "ready";
  return (
    <aside className="status-dock" aria-label="Runtime status">
      <div className="status-line">
        <span className={ready ? "badge ready" : "badge not-ready"}>
          {ready ? "Ready" : "Degraded"}
        </span>
        <span>{busy?.label ?? notice}</span>
      </div>
      <div className="dependency-chips">
        {(meta?.dependencies ?? []).map((dependency) => (
          <span
            className={dependency.ok ? "chip online" : "chip offline"}
            key={dependency.name}
          >
            {dependency.name}: {dependency.ok ? "online" : "offline"}
          </span>
        ))}
        {capabilities?.capabilities.slice(0, 3).map((capability) => (
          <span className="chip" key={capability.key}>
            {capability.label}
          </span>
        ))}
      </div>
    </aside>
  );
}

function ControlButton({
  children,
  onClick,
  disabled,
  tone = "neutral",
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  tone?: "neutral" | "primary" | "danger";
}) {
  return (
    <button
      className={`button ${tone}`}
      type="button"
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

function MetricTile({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="metric-tile">
      <span>{label}</span>
      <strong>
        {typeof value === "number" ? value.toLocaleString() : value}
      </strong>
    </div>
  );
}

export function MiniBars({
  series,
  definition,
}: {
  series: MetricsSeriesResponse | null;
  definition?: MetricDefinition;
}) {
  const points = series?.items ?? [];
  const values = points.map((point) =>
    point.value === null ? null : Number(point.value),
  );
  const numeric = values.filter(
    (value): value is number => value !== null && Number.isFinite(value),
  );
  const min = Math.min(0, ...numeric);
  const max = Math.max(0, ...numeric);
  const range = max - min || 1;
  const label = definition?.label ?? series?.metric ?? "Metric";
  const caption = `${label} by day (${series?.timezone ?? "UTC"})`;
  return (
    <figure className="metric-series">
      <figcaption className="detail">{caption}</figcaption>
      {points.length === 0 ? (
        <p className="detail">No observations</p>
      ) : (
        <ul className="mini-bars" aria-label={caption}>
          {points.map((point, index) => {
            const value = values[index];
            const available = value !== null && Number.isFinite(value);
            const display = available
              ? formatSeriesValue(value, definition?.unit)
              : "unavailable";
            const description = `${point.timestamp.slice(0, 10)}: ${label}: ${display}`;
            return (
              <li
                key={point.timestamp}
                title={description}
                aria-label={description}
                tabIndex={0}
              >
                <span
                  className="metric-zero"
                  aria-hidden="true"
                  style={{ bottom: `${(-min / range) * 100}%` }}
                />
                {available ? (
                  <span
                    className="metric-bar"
                    aria-hidden="true"
                    data-sign={value < 0 ? "negative" : "nonnegative"}
                    style={{
                      height: `${(Math.abs(value) / range) * 100}%`,
                      bottom: `${((Math.min(0, value) - min) / range) * 100}%`,
                    }}
                  />
                ) : (
                  <span className="metric-unavailable">n/a</span>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {series?.completeness_warnings.map((warning) => (
        <p className="detail" key={warning}>
          {warning}
        </p>
      ))}
    </figure>
  );
}

function formatSeriesValue(
  value: number,
  unit?: MetricDefinition["unit"],
): string {
  if (unit === "minor_money" || unit === "money") {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
    }).format(unit === "minor_money" ? value / 100 : value);
  }
  if (unit === "rate") {
    return new Intl.NumberFormat("en-US", {
      style: "percent",
      maximumFractionDigits: 2,
    }).format(value);
  }
  return value.toLocaleString("en-US");
}

export function SearchResultRow({ candidate }: { candidate: RankedCandidate }) {
  const checks = Object.entries(candidate.constraint_matches);
  const failed = checks.filter(([, passed]) => !passed).map(([name]) => name);
  return (
    <article className="search-result">
      <div>
        <p className="label">{candidate.title}</p>
        <p className="detail">{candidate.category_path.join(" / ")}</p>
      </div>
      <div>
        <strong>
          {formatMoney(candidate.price.amount_minor, candidate.price.currency)}
        </strong>
        <span>{candidate.score} score</span>
      </div>
      <p className="search-evidence">
        Relevance {candidate.score_components.relevance} / Goal boost{" "}
        {candidate.score_components.goal_boost ?? "Not recorded"}
        <br />
        Hard filters:{" "}
        {checks.length === 0
          ? "Not recorded"
          : failed.length > 0
            ? `FAIL: ${failed.join(", ")}`
            : `${checks.length} passed`}
      </p>
    </article>
  );
}

export function resetGoalPayload(
  goal: GoalRecord,
  seed: number,
): GoalCreateRequest {
  return {
    name: goal.spec.name,
    scenario_id: goal.scenario_id,
    seed,
    objective_metric: goal.spec.objective.metric,
    objective_direction: goal.spec.objective.direction,
    objective_scope: goal.spec.objective.scope,
    target_value: goal.spec.objective.target,
    horizon_days: Math.ceil(
      (Date.parse(goal.spec.horizon.end_at) -
        Date.parse(goal.spec.horizon.start_at)) /
        86400000,
    ),
    budget: goal.spec.budgets.find((budget) => budget.kind === "goal")?.amount,
    daily_budget: goal.spec.budgets.find((budget) => budget.kind === "daily")
      ?.amount,
    default_mode: goal.spec.autonomy.default_mode,
    per_action_modes: goal.spec.autonomy.per_action,
    allowed_action_types: goal.spec.allowed_action_types,
    constraints: goal.spec.constraints,
    merchandising: goal.spec.merchandising,
    soft_preferences: goal.soft_preferences,
    planning_mode: goal.planning_mode,
  };
}

export function idempotencyKey(
  prefix: string,
  ...parts: Array<number | string | null | undefined>
): string {
  const scope = parts
    .filter(
      (part) => part !== null && part !== undefined && String(part).length > 0,
    )
    .map((part) => String(part).replace(/[^A-Za-z0-9._:-]/g, "-"))
    .join("-");
  return [prefix, scope, crypto.randomUUID()].filter(Boolean).join("-");
}

function formatMoney(amountMinor: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amountMinor / 100);
}

function formatOptionalMoney(amountMinor: number | null | undefined): string {
  return amountMinor === null || amountMinor === undefined
    ? "n/a"
    : formatMoney(amountMinor);
}

function formatRate(value: string | undefined): string {
  if (!value) {
    return "Not measured";
  }
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  }).format(new Date(value));
}

function shortId(value: string): string {
  return value.slice(0, 8);
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function statusBadge(statusValue: ActionStatus | undefined): string {
  if (
    statusValue === "denied" ||
    statusValue === "failed" ||
    statusValue === "rollback_failed"
  ) {
    return "badge danger";
  }
  if (
    statusValue === "awaiting_approval" ||
    statusValue === "approved" ||
    statusValue === "executable"
  ) {
    return "badge warning";
  }
  if (statusValue === "succeeded" || statusValue === "rolled_back") {
    return "badge ready";
  }
  return "badge info";
}

function policyYaml(policy: ControllerPolicyConfig | null): string {
  if (!policy) {
    return "policy_version: 1\nstatus: not_loaded\n";
  }
  return [
    `policy_version: ${policy.policy_version}`,
    `default_mode: ${policy.default_mode}`,
    `kill_switch_enabled: ${policy.kill_switch_enabled}`,
    `discount_max_percentage: ${policy.discount_max_percentage}`,
    `search_boost_max_multiplier: ${policy.search_boost_max_multiplier}`,
    `max_actions_per_run: ${policy.max_actions_per_run}`,
  ].join("\n");
}
