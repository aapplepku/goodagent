# Agent Runtime

## Current release-candidate behavior

The durable simulator planner uses a typed, persisted goal assessment. Acquisition
defaults to new customers; excess inventory defaults to units sold from the
original excess-stock cohort; the search scenario uses search-attributed purchase
counts, not a fabricated search conversion rate. Explicit objectives support
revenue, contribution profit, CAC, store conversion, contribution margin, and
discount rate. Money is in integer minor units and rates are fractions. Missing
denominators produce `null`, not zero. Search conversion rate and inventory days
of supply are rejected because this simulator does not measure their denominators.

Progress uses cumulative non-history observations. A recent-seven-day rate
heuristic describes trajectory, with historical data explicitly labeled when no
current outcome exists. It is not calibrated or causal. Only a count target above
current progress plus all remaining eligible inventory is classified as infeasible.
Such a goal records an explanation and produces no write proposals.

An acquisition goal on track proposes a reversible campaign-cost experiment;
an at-risk acquisition goal proposes a bounded welcome offer and search exposure.
An at-risk excess-stock goal limits its discount and search targets to stocked
excess products. A search-purchase goal proposes search exposure, not an unrelated
welcome offer. The compiler still resolves current products and policy facts;
these hypotheses are not permission to execute. Deliberately excessive proposals
belong in adversarial tests, not the normal planner. No strategy is guaranteed to
outperform the untreated simulator, and benchmark results must report losses too.

The design sections below describe the broader runtime architecture. They are not
evidence that every proposed detector, causal estimator, or live connector exists.

## 1. Purpose

The runtime turns a merchant goal into a sequence of observable, policy-compliant commerce actions.

It is a **closed-loop controller**, not a free-form chatbot:

```text
goal
  ↓
observe current state
  ↓
detect opportunities
  ↓
generate typed candidate actions
  ↓
estimate impact and risk
  ↓
select a feasible action portfolio
  ↓
approve or execute
  ↓
measure outcomes
  ↓
learn and repeat
```

The first implementation uses one orchestrating graph. Do not begin with a society of conversational sub-agents. Specialized components may have names such as `OpportunityDetector`, `PriceAnalyzer`, or `DiscountPlanner`, but they should exchange typed objects, not prose.

## 2. Runtime boundaries

### The LLM may

- turn a natural-language merchant request into a draft `GoalSpec`;
- summarize a store snapshot;
- propose business hypotheses;
- map vague language to a finite set of supported action intents;
- explain deterministic model outputs;
- parse complex shopping queries into structured constraints;
- critique a search result set.

### The LLM may not

- calculate authoritative money totals;
- decide that a hard constraint can be ignored;
- write directly to Shopify, an ad platform, or a database;
- invent product, order, customer, inventory, or campaign facts;
- execute SQL;
- evaluate arbitrary user-supplied expressions;
- select an unsupported action type;
- approve its own high-risk proposal;
- receive raw PII, secrets, or access tokens.

All quantities used for budget enforcement, margin checks, eligibility, and execution are recalculated by deterministic code from authoritative data.

## 3. Core types

Implement these as Pydantic models in the domain package.

### `GoalSpec`

```python
class GoalSpec(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    objective: ObjectiveSpec
    horizon: HorizonSpec
    budgets: list[BudgetSpec]
    constraints: list[ConstraintSpec]
    autonomy: AutonomyPolicy
    allowed_action_types: set[ActionType]
    evaluation_schedule: EvaluationSchedule
    status: GoalStatus
    created_at: datetime
```

Example:

```yaml
name: New customer growth
objective:
  metric: new_customers
  direction: maximize
  target: 200
horizon:
  start_at: 2026-09-01T00:00:00Z
  end_at: 2026-09-30T23:59:59Z
budgets:
  - kind: total_acquisition_and_promotion
    amount_minor: 1000000
    currency: USD
constraints:
  - metric: cac
    operator: lte
    value: 40
  - metric: contribution_margin_rate
    operator: gte
    value: 0.25
  - metric: discount_rate
    operator: lte
    value: 0.15
autonomy:
  default_mode: approval_required
  per_action:
    create_discount: bounded_auto
    set_variant_price: approval_required
allowed_action_types:
  - create_discount
  - disable_discount
  - set_search_boost
  - set_campaign_budget
```

Do not parse arbitrary constraint expressions at runtime. `operator` must be an enum, and `metric` must come from a registry with an explicit evaluator.

### `ObservationSnapshot`

This is the immutable, time-stamped input to one planning cycle.

```python
class ObservationSnapshot(BaseModel):
    tenant_id: UUID
    goal_id: UUID
    as_of: datetime
    data_freshness: dict[DataSource, FreshnessStatus]
    metric_values: dict[MetricName, Decimal]
    metric_series_refs: dict[MetricName, UUID]
    catalog_summary: CatalogSummary
    inventory_summary: InventorySummary
    customer_summary: CustomerSummary | None
    channel_summary: ChannelSummary | None
    active_interventions: list[ActiveIntervention]
    unresolved_actions: list[ActionSummary]
    confidence: ConfidenceSummary
```

Store the full snapshot or a content-addressed reference so every run is reproducible.

### `Opportunity`

```python
class Opportunity(BaseModel):
    type: OpportunityType
    entity_refs: list[EntityRef]
    evidence: list[EvidenceItem]
    estimated_value_minor: int | None
    confidence: float
    eligible_action_types: set[ActionType]
    diagnostic_code: str
```

Examples:

- underperforming new-customer conversion;
- excess inventory with healthy margin;
- high-spend campaign above CAC constraint;
- high-relevance product receiving little search exposure;
- expiring promotion;
- low-stock product still receiving aggressive promotion.

Opportunity detection should be deterministic whenever possible.

### Typed `ActionIntent`

Use a discriminated union:

```python
ActionIntent = Annotated[
    CreateDiscountIntent
    | DisableDiscountIntent
    | SetVariantPriceIntent
    | SetSearchBoostIntent
    | SetCampaignBudgetIntent
    | NoOpIntent,
    Field(discriminator="type"),
]
```

Common fields:

```python
class ActionIntentBase(BaseModel):
    type: ActionType
    rationale: str
    opportunity_ids: list[UUID]
    requested_by: ActorRef
    source_run_id: UUID
    proposed_at: datetime
```

Intent-specific fields must be explicit. For example:

```python
class CreateDiscountIntent(ActionIntentBase):
    type: Literal["create_discount"]
    discount_kind: Literal["percentage", "fixed_amount"]
    value: Decimal
    starts_at: datetime
    ends_at: datetime
    product_scope: ProductScope
    customer_scope: CustomerScope
    minimum_subtotal_minor: int | None
    code: str | None
```

### `CompiledAction`

The compiler resolves an intent against current authoritative state.

```python
class CompiledAction(BaseModel):
    id: UUID
    intent: ActionIntent
    target_provider: ProviderRef
    normalized_parameters: dict[str, JSONValue]
    preconditions: list[Precondition]
    expected_impact: ImpactEstimate
    estimated_cost_minor: int
    budget_reservations: list[BudgetReservationRequest]
    risk: RiskAssessment
    rollback_plan: RollbackPlan
    idempotency_key: str
    expires_at: datetime
```

The `idempotency_key` should be stable for the same tenant, intent type, target entities, normalized parameters, and logical planning window.

### `PolicyDecision`

```python
class PolicyDecision(BaseModel):
    outcome: Literal["allow", "require_approval", "deny"]
    reason_codes: list[str]
    evaluated_rules: list[RuleEvaluation]
    required_approver_roles: set[Role]
    valid_until: datetime
```

### `ActionResult`

```python
class ActionResult(BaseModel):
    action_id: UUID
    provider_request_id: str | None
    status: ExecutionStatus
    before_state: dict[str, JSONValue]
    after_state: dict[str, JSONValue]
    started_at: datetime
    completed_at: datetime | None
    error: SafeError | None
    reconciliation_required: bool
```

## 4. LangGraph workflow

Use LangGraph as the orchestration layer and PostgreSQL-backed persistence for restartable state. The graph should be deterministic around external side effects: a resumed node must not repeat an already-recorded write.

Suggested graph:

```text
START
  ↓
load_goal_and_policy
  ↓
acquire_goal_run_lock
  ↓
validate_integrations
  ↓
check_data_freshness
  ├── stale → enqueue_sync → wait_or_end
  └── fresh
        ↓
build_observation_snapshot
        ↓
detect_opportunities
        ↓
generate_hypotheses
        ↓
generate_action_intents
        ↓
compile_actions
        ↓
estimate_and_simulate
        ↓
evaluate_policies
        ↓
select_action_portfolio
        ↓
persist_proposals
        ├── all denied/no-op → summarize → END
        ├── approval needed → INTERRUPT
        └── bounded auto
               ↓
execute_actions
        ↓
reconcile_provider_state
        ↓
schedule_measurement_windows
        ↓
summarize_run
        ↓
END
```

Outcome evaluation is a separate scheduled graph:

```text
load_due_interventions
  ↓
build_pre/post metrics
  ↓
estimate observed lift
  ↓
check guardrails
  ├── severe regression → rollback candidate / emergency disable
  └── acceptable
        ↓
update experiment ledger
        ↓
update action priors
        ↓
schedule next planning run
```

## 5. Graph state

Keep state small and persist large payloads in PostgreSQL/object storage.

```python
class CommerceGraphState(TypedDict, total=False):
    tenant_id: str
    goal_id: str
    run_id: str
    trigger: dict
    observation_snapshot_id: str
    opportunity_ids: list[str]
    intent_ids: list[str]
    compiled_action_ids: list[str]
    policy_decision_ids: list[str]
    selected_action_ids: list[str]
    approval_request_ids: list[str]
    execution_ids: list[str]
    warnings: list[str]
    summary: str
```

Never place access tokens, raw webhook payloads containing PII, or large product arrays in graph state.

Use one stable `thread_id` per goal and one distinct `checkpoint_ns` or run identifier per planning cycle. Persist the domain records before advancing the checkpoint around any external write.

## 6. Node design rules

Each graph node should:

1. accept typed state and a typed dependency container;
2. load required domain records using tenant-scoped repositories;
3. perform one conceptual operation;
4. persist its outputs transactionally;
5. return IDs and small status fields;
6. be safe to rerun;
7. emit structured tracing spans;
8. never hide a partial failure.

Nodes that call LLMs must:

- use strict structured output;
- cap input size;
- include only authorized data;
- label merchant/catalog text as untrusted;
- validate the output against enums and limits;
- retry malformed output at most once with a validation error;
- fall back to deterministic/no-op behavior;
- log token/cost metadata without logging sensitive prompt contents.

## 7. Opportunity detection

Implement a registry:

```python
class OpportunityDetector(Protocol):
    code: str
    required_capabilities: set[Capability]

    async def detect(
        self,
        goal: GoalSpec,
        snapshot: ObservationSnapshot,
    ) -> list[Opportunity]: ...
```

Initial detectors:

1. `NewCustomerConversionGapDetector`
   - needs new/returning cohort metrics;
   - compares current rate with trailing baseline;
   - proposes discount or acquisition-budget actions only if sample thresholds pass.

2. `ExcessInventoryDetector`
   - uses days of supply, stock age, sell-through, margin, and active promotion state;
   - excludes unavailable or low-margin products.

3. `CampaignCACViolationDetector`
   - simulator first; real implementation after an ads connector;
   - identifies spend above goal constraints.

4. `SearchExposureGapDetector`
   - detects products with high predicted relevance/conversion but low exposure in the project's own search surface.

5. `GuardrailRiskDetector`
   - identifies active actions approaching budget, margin, stock, or error thresholds;
   - can produce disable/rollback intents.

Each detector needs unit tests with boundary cases and a deterministic diagnostic code.

## 8. Hypothesis generation

The LLM receives a compact, structured summary of detected opportunities and may return:

```python
class Hypothesis(BaseModel):
    opportunity_id: UUID
    claim: str
    supporting_evidence_ids: list[UUID]
    counter_evidence_ids: list[UUID]
    candidate_action_types: list[ActionType]
    uncertainty: str
```

It must not introduce facts not represented by evidence IDs. Unsupported hypotheses are rejected.

For straightforward opportunities, skip the LLM entirely and use a deterministic template.

## 9. Action compilation

Use one compiler per action type:

```python
class ActionCompiler(Protocol):
    action_type: ActionType

    async def compile(
        self,
        intent: ActionIntent,
        context: CompileContext,
    ) -> CompiledAction: ...
```

Examples:

- `CreateDiscountCompiler` confirms selected products, current prices, cost basis, margin floors, dates, code collision, and discount stacking policy.
- `SetVariantPriceCompiler` rereads each current variant price, validates maximum delta, snapshots rollback values, and computes projected margin.
- `SetSearchBoostCompiler` checks that the tenant uses this project's search surface and that all targets pass a minimum relevance threshold.
- `SetCampaignBudgetCompiler` verifies provider capability, current budget, remaining goal budget, and provider limits.

A compiler must fail closed when data is absent or stale.

## 10. Impact estimation

MVP estimates should be simple, inspectable, and conservative.

Implement:

```python
class ImpactEstimator(Protocol):
    action_type: ActionType

    async def estimate(
        self,
        action: CompiledActionDraft,
        snapshot: ObservationSnapshot,
    ) -> ImpactEstimate: ...
```

Initial methods:

- discount: historical elasticity if available; otherwise configured conservative prior and a wide confidence interval;
- price: no autonomous execution; estimate only, using configured elasticity bands;
- search boost: estimate exposure delta × conversion probability × margin, capped by historical traffic;
- campaign budget: simulator response curves; later provider historical marginal CAC curves.

Store:

- point estimate;
- lower/upper interval;
- model/version;
- feature snapshot reference;
- assumptions;
- out-of-distribution flags.

Never present an LLM estimate as a quantitative impact estimate.

## 11. Portfolio selection

The controller may have multiple candidate actions but one shared budget.

MVP algorithm:

1. discard denied, expired, low-confidence, and duplicate actions;
2. reserve mandatory guardrail actions first;
3. compute a conservative utility using the lower confidence bound;
4. rank by constrained utility per unit of budget;
5. greedily add actions while checking:
   - budget;
   - action count;
   - target conflicts;
   - cooldowns;
   - provider rate limits;
   - exposure overlap;
6. mark non-selected actions with an explicit reason.

Later, replace the greedy selector behind an interface with OR-Tools or a contextual bandit. Do not couple the graph to the selection algorithm.

## 12. Approval interrupts

When an action requires approval:

1. persist the proposal and policy result;
2. create an `approval_request`;
3. interrupt the graph;
4. show the complete action diff, expected impact, assumptions, policy checks, expiration, and rollback;
5. on approve/reject, resume the exact graph thread;
6. recompile and re-run policy checks immediately before execution because state may have changed.

Approval is not a blanket bypass. A newly violated hard constraint must deny execution even after approval.

## 13. Execution protocol

For every write:

```text
begin transaction
  ↓
lock action row
  ↓
confirm status is executable
  ↓
re-read provider state
  ↓
evaluate preconditions and policy
  ↓
reserve budget
  ↓
record execution attempt
commit
  ↓
call provider with idempotency protections
  ↓
persist response
  ↓
re-read/reconcile remote state
  ↓
mark succeeded / failed / uncertain
```

Never automatically retry an external write when the first result is ambiguous unless reconciliation proves the write did not happen.

Retries:

- safe reads: exponential backoff with jitter;
- idempotent writes: bounded retry;
- ambiguous writes: reconcile first;
- validation errors: no retry;
- authentication errors: disable connector and alert;
- policy failure: no retry until the state or policy changes.

## 14. Run memory

Store three distinct forms of memory:

1. **Authoritative history**
   - actions, metrics, approvals, and outcomes in domain tables.

2. **Experiment/action priors**
   - per action type, category, segment, and tenant;
   - machine-readable numeric outcomes.

3. **Narrative summaries**
   - LLM-generated convenience summaries;
   - never authoritative and always linked to source records.

Do not add a general vector memory system to the MVP. Search over audit records can be added later.

## 15. Scheduling and concurrency

MVP:

- Redis-backed worker queue;
- periodic scheduler enqueues goal runs;
- PostgreSQL advisory lock or unique active-run constraint per goal;
- separate queue for connector syncs and action execution;
- maximum one active planning run per goal;
- maximum one active write against the same remote entity;
- provider-level concurrency and rate-limit controls.

The simulator may advance virtual time rapidly. Real stores use wall-clock scheduling.

## 16. Failure behavior

The safe fallback is always:

```text
no write
+ explicit degraded status
+ actionable error
+ retained trace
```

Required failure states:

- data stale;
- missing capability;
- provider authentication expired;
- policy configuration invalid;
- insufficient sample size;
- impact model unavailable;
- external write uncertain;
- reconciliation mismatch;
- budget reservation conflict;
- graph resume failure.

## 17. Acceptance criteria

The runtime is complete for the MVP when:

- every run can be resumed after process termination;
- no graph node directly calls a provider write except `execute_actions`;
- malformed LLM output cannot reach a provider;
- every proposal links to observations, opportunities, assumptions, policy decisions, and rollback;
- an approval interrupt resumes the same run;
- rerunning an execution node does not duplicate a discount or price change;
- a kill switch blocks new writes immediately;
- a simulator goal can run through repeated observe/act/measure cycles;
- shadow-mode Shopify goals create proposals but no remote writes.
