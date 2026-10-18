# Frontend and Trace UI

## 1. Product experience

The UI has two jobs:

1. make the simulator immediately impressive;
2. make real-store autonomy trustworthy.

The main product is not a chat box. The main product is a goal dashboard with an inspectable action trace.

Use Next.js and strict TypeScript. Consume generated API types. Keep business/policy logic in the backend.

## 2. Information architecture

```text
/
├── demo
├── onboarding
├── overview
├── goals
│   ├── new
│   └── [goalId]
├── runs
│   └── [runId]
├── actions
│   └── [actionId]
├── search
├── catalog
├── integrations
├── policy
├── audit
└── settings
```

## 3. Demo landing page

The public/local landing page should communicate the product in one screen:

```text
Give an AI agent a business goal.
Watch it run a simulated store within your rules.

[Run acquisition scenario]
[Run excess-inventory scenario]
[Connect Shopify in shadow mode]
```

Show a small animated loop:

```text
Observe → Decide → Act → Measure
```

Do not lead with framework names or architecture jargon.

## 4. Simulator workspace

Layout:

### Header

- scenario name/version;
- seed;
- virtual date;
- play/pause;
- advance one day;
- run to end;
- reset;
- kill switch.

### Left column: goal and constraints

- primary objective measurements and target, with the server-provided assessment;
  no inferred completion percentage (a ratio can reverse minimizing objectives);
- horizon;
- total budget;
- CAC ceiling;
- margin floor;
- discount limit;
- autonomy badges.

### Center: timeline

Chronological event cards:

- observation;
- opportunity;
- hypothesis;
- proposed action;
- policy decision;
- approval;
- execution;
- outcome;
- rollback.

Each card expands into evidence and machine-readable details.

### Right column: current state

- campaigns and budgets;
- active discounts;
- price changes;
- search boosts;
- inventory warnings;
- pending approvals.

### Bottom: outcomes

- no-agent baseline vs agent;
- new customers;
- CAC;
- contribution margin;
- budget use;
- cumulative profit;
- constraint violations.

## 5. Goal creation wizard

Steps:

1. **Objective**
   - select supported metric;
   - maximize/minimize/reach target;
   - optional natural-language draft.

2. **Horizon**
   - dates;
   - cadence;
   - timezone.

3. **Budget**
   - amount/currency;
   - budget types.

4. **Constraints**
   - metric/operator/value from supported registry;
   - explain each metric definition.

5. **Allowed actions**
   - discounts;
   - search boosts;
   - campaign budget;
   - price proposals.

6. **Autonomy**
   - shadow;
   - require approval;
   - bounded auto by action.

7. **Review**
   - capability gaps;
   - policies;
   - exact goal JSON;
   - activate.

Natural-language parsing only pre-fills the form. The merchant confirms structured values.

## 6. Overview dashboard

Cards:

- active goals;
- progress vs target;
- current constraints;
- budget remaining;
- actions today;
- pending approvals;
- integration freshness;
- open warnings.

Charts:

- objective metric over time;
- CAC and margin guardrails;
- spend/budget;
- action outcome history.

Always show data freshness and metric definition links.

Simulator metric series preserve unavailable observations as JSON `null`, not
zero (notably CAC when there are no new customers). A page with null observations
includes a completeness warning. The chart uses the selected metric definition,
UTC dates and appropriate units, with a zero baseline for signed profit values.
An empty series has no fabricated bars. `units_sold` and `revenue` series report
whole-store totals; the units chart explicitly says whole store and does not
represent excess-inventory objective attainment. Goal assessment remains the
separate authoritative, scope-aware controller measurement.

## 7. Run trace

This is the signature UI.

Example:

```text
09:00  OBSERVED
       Paid social CAC = $61.40; goal maximum = $40.
       1,204 sessions; 19 attributed new customers.

09:00  OPPORTUNITY
       Reallocate acquisition budget.
       Confidence: 0.87.

09:01  PROPOSED
       Reduce Campaign C daily budget by 20%.
       Increase Campaign A by 12%.

09:01  POLICY
       Campaign C decrease: allowed.
       Campaign A increase: approval required.
       Reason: daily increase exceeds bounded-auto allowance.

09:04  APPROVED by Emma

09:04  EXECUTED
       Remote state reconciled.

Day 4 OUTCOME
       CAC changed from $45.20 to $38.70.
       Margin remains 27.1%.
```

Trace requirements:

- ordered and timestamped;
- source evidence links;
- model/policy versions;
- deterministic vs LLM badge;
- latency/cost in debug mode;
- copy trace as JSON;
- no hidden chain-of-thought;
- show concise explanations and recorded evidence, not private model reasoning.

## 8. Action detail and approval

Sections:

1. **What will change**
   - exact before/after values;
   - affected products/campaigns;
   - remote provider.

2. **Why**
   - opportunity/evidence;
   - goal relationship.

3. **Expected effect**
   - point estimate and interval;
   - assumptions;
   - data volume.

4. **Policy**
   - passed/failed checks;
   - risk tier;
   - required role.

5. **Cost**
   - budget reservation;
   - worst-case configured exposure.

6. **Monitoring**
   - window;
   - primary metric;
   - guardrails.

7. **Rollback**
   - exact rollback action;
   - limitations.

Actions:

- approve;
- reject with reason;
- edit by creating a new proposal;
- cancel;
- rollback after execution.

Never support silently editing an approved action in place.

## 9. Policy editor

Use a form for common policies and an advanced YAML view.

Features:

- schema validation;
- diff against current version;
- warnings for broader autonomy;
- dry-run against recent proposals;
- preview which actions would become allowed/denied;
- owner confirmation;
- version history and restore.

Kill switch is separate, always visible, and not buried in policy YAML.

## 10. Integration onboarding

### Simulator

One click: choose scenario and seed.

### Shopify

Steps:

1. explain shadow mode;
2. select custom-token or OAuth mode;
3. connect;
4. show granted capabilities/scopes;
5. run sync;
6. show record counts and freshness;
7. start first shadow goal;
8. separately enable approved writes later.

Do not prompt for broad scopes before their feature is enabled.

## 11. Search playground

Inputs:

- query;
- filters;
- mode: sparse/dense/hybrid/hybrid+reranker;
- optional goal context;
- top K;
- debug toggle.

Outputs:

- parsed intent;
- hard/preferred/excluded constraints;
- retrieval branch counts;
- retries;
- result cards;
- score decomposition;
- latency;
- query/ranking version.

Comparison mode places configurations side by side and runs benchmark labels when available.

## 12. Catalog pages

Product list:

- title/category/brand;
- current price;
- margin availability;
- stock;
- index status;
- source updated time;
- active actions.

Product detail:

- variants;
- price/cost/margin;
- inventory;
- search document preview;
- current boosts;
- recent impressions/clicks/orders;
- intervention history;
- source vs normalized diff.

Hide unit cost from shopper-facing routes.

## 13. Audit page

Filter by:

- time;
- actor;
- event type;
- action;
- run;
- provider;
- status.

Audit export must redact secrets and PII. Show immutable event IDs/hashes where available.

## 14. UI state and data fetching

Current simulator workspace: reads are sequence- and goal-scoped. Starting an
operator mutation invalidates in-flight background responses synchronously, so
an older poll cannot overwrite the acknowledged kill-switch or policy state.
The production E2E deliberately delivers an old kill-switch read after enabling
the switch, then verifies an explicit disable actually leaves the API disabled.
Creation and activation select the persisted goal before requesting the next
mutation. If planning is refused (for example, by an enabled kill switch), the
new goal remains selected in the URL and saved-goal list; it is not reported as
successfully planned and can be resumed explicitly after resolving the cause.

- use generated OpenAPI client;
- TanStack Query or equivalent for server state;
- server-sent events for live run updates;
- optimistic updates only for safe local UI state, not external action success;
- actions remain “executing” until backend reconciliation;
- every page handles stale/degraded/empty/error states;
- show request ID for support.

## 15. Accessibility and responsive behavior

- keyboard-accessible approval controls;
- focus management in dialogs;
- semantic headings;
- screen-reader labels on charts and policy results;
- non-color indicators for allow/deny/warning;
- desktop-first dashboard but usable on tablet;
- critical kill switch usable on mobile.

## 16. Visual design

Aim for:

- operational control-room clarity;
- neutral palette;
- high information density without clutter;
- prominent status and risk;
- minimal decoration;
- consistent badges:
  - deterministic;
  - model-assisted;
  - shadow;
  - approval;
  - auto;
  - denied;
  - rolled back.

Do not present generated estimates as precise facts. Use intervals and confidence labels.

## 17. Frontend test plan

Unit/component:

- goal form validation;
- money rendering;
- policy diff;
- action state transitions;
- permission-gated buttons;
- trace step rendering;
- error/empty/stale states.

End-to-end:

1. launch simulator;
2. create goal;
3. advance a day;
4. inspect denied action;
5. approve proposal;
6. observe execution;
7. enable kill switch;
8. confirm future action blocked;
9. reset scenario;
10. search and inspect hybrid trace.

Shopify smoke:

- connect dev store;
- complete sync;
- display shadow proposal;
- no write buttons when scopes/mode disallow them.

## 18. Definition of done

- a new user reaches a running simulator in under five minutes;
- goal constraints and budget remain visible;
- every action has an understandable trace;
- approval shows exact diff and rollback;
- no UI state claims external success before reconciliation;
- kill switch is always accessible;
- search playground exposes technical differentiation;
- operator and viewer roles see appropriate controls;
- core flows pass Playwright tests.
