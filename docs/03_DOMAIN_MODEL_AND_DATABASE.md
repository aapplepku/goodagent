# Domain Model and Database

## 1. Conventions

- money: integer minor units plus ISO-4217 currency;
- calculations: `Decimal`, never binary float;
- timestamps: timezone-aware UTC in storage;
- API enum values: lower `snake_case`;
- every tenant-owned row has `tenant_id`;
- source/provider IDs are opaque strings;
- mutable records have `version` and `updated_at`;
- authoritative state is normalized; large raw payloads are minimized and short-lived;
- events/audit rows are append-only;
- model text is not authoritative data.

## 2. Core value objects

```python
class Money(BaseModel):
    amount_minor: int
    currency: str

class TimeWindow(BaseModel):
    start_at: datetime
    end_at: datetime

class MetricPoint(BaseModel):
    metric: MetricName
    value: Decimal
    unit: MetricUnit
    window: TimeWindow
    dimensions: dict[str, str]
    definition_version: str
    freshness_at: datetime

class ConfidenceInterval(BaseModel):
    lower: Decimal
    point: Decimal
    upper: Decimal
    level: Decimal
```

Never aggregate different currencies without an explicit FX fact and policy.

## 3. Goal model

Use the `GoalSpec` shape in `docs/04_AGENT_RUNTIME.md`.

Canonical objective metrics initially:

- `new_customers`;
- `revenue`;
- `contribution_profit`;
- `contribution_margin_rate`;
- `units_sold`;
- `inventory_days_of_supply`;
- `search_conversion_rate`;
- `search_attributed_purchases`.

Operators:

- `lt`;
- `lte`;
- `eq`;
- `gte`;
- `gt`.

A metric registry maps each enum to:

- unit;
- definition/version;
- required capabilities;
- allowed operators;
- evaluator;
- minimum data rules.

## 4. Snapshot and evidence

An agent run reasons over a versioned immutable snapshot, not ad hoc query results.

```python
class ObservationSnapshot(BaseModel):
    id: UUID
    tenant_id: UUID
    goal_id: UUID
    as_of: datetime
    data_freshness: dict[DataSource, FreshnessStatus]
    metric_values: dict[MetricName, Decimal]
    catalog_summary: CatalogSummary
    inventory_summary: InventorySummary
    customer_summary: CustomerSummary | None
    channel_summary: ChannelSummary | None
    active_interventions: list[ActiveIntervention]
    unresolved_actions: list[ActionSummary]
    confidence: ConfidenceSummary
    content_hash: str
```

Evidence records point to a snapshot, metric series, product set, campaign, or intervention. An LLM hypothesis must cite evidence IDs that exist.

## 5. Actions

Use the typed `ActionIntent` discriminated union and `CompiledAction` from `docs/04_AGENT_RUNTIME.md`.

Initial action values:

- `create_discount`;
- `disable_discount`;
- `set_variant_price`;
- `set_search_boost`;
- `set_campaign_budget`;
- `no_op`.

`set_campaign_budget` maps to a simulator provider first and a real ads provider later.

### Action states

```text
draft
  → compiled
  → denied
  → awaiting_approval
  → approved
  → executable
  → executing
  → succeeded | failed | uncertain
  → evaluating
  → completed | rollback_proposed
  → rolling_back
  → rolled_back | rollback_failed

Additional terminal/side states:
expired
cancelled
```

The state machine explicitly defines valid transitions. There is no generic status update.

## 6. Identity and tenancy tables

```text
tenants
  id UUID PK
  slug TEXT UNIQUE
  display_name TEXT
  default_currency CHAR(3)
  timezone TEXT
  status TEXT
  created_at TIMESTAMPTZ
  updated_at TIMESTAMPTZ
  version INT

users
  id UUID PK
  external_subject TEXT UNIQUE
  email_hash TEXT NULL
  created_at TIMESTAMPTZ

tenant_memberships
  tenant_id UUID
  user_id UUID
  role TEXT
  created_at TIMESTAMPTZ
  PRIMARY KEY (tenant_id, user_id)
```

Do not build password storage. Production identity comes from an OIDC provider.

## 7. Integrations and credentials

```text
integrations
  id UUID PK
  tenant_id UUID
  provider TEXT
  external_account_id TEXT
  display_name TEXT
  mode TEXT
  status TEXT
  capabilities JSONB
  non_secret_config JSONB
  last_successful_sync_at TIMESTAMPTZ NULL
  created_at TIMESTAMPTZ
  updated_at TIMESTAMPTZ
  version INT
  UNIQUE (tenant_id, provider, external_account_id)

integration_credentials
  id UUID PK
  tenant_id UUID
  integration_id UUID UNIQUE
  ciphertext BYTEA
  key_version TEXT
  expires_at TIMESTAMPTZ NULL
  refresh_metadata JSONB
  created_at TIMESTAMPTZ
  rotated_at TIMESTAMPTZ NULL
```

`refresh_metadata` contains no refresh token; all secret material stays inside ciphertext.

## 8. Catalog

```text
products
  id UUID PK
  tenant_id UUID
  integration_id UUID
  source_product_id TEXT
  title TEXT
  handle TEXT NULL
  description_text TEXT
  brand TEXT NULL
  category_path TEXT[]
  tags TEXT[]
  status TEXT
  attributes JSONB
  primary_image_url TEXT NULL
  product_url TEXT NULL
  source_updated_at TIMESTAMPTZ
  synced_at TIMESTAMPTZ
  content_hash TEXT
  version INT
  UNIQUE (tenant_id, integration_id, source_product_id)

product_variants
  id UUID PK
  tenant_id UUID
  product_id UUID
  source_variant_id TEXT
  sku TEXT NULL
  title TEXT
  option_values JSONB
  price_minor BIGINT
  compare_at_price_minor BIGINT NULL
  cost_minor BIGINT NULL
  currency CHAR(3)
  available BOOLEAN
  source_updated_at TIMESTAMPTZ
  content_hash TEXT
  version INT
  UNIQUE (tenant_id, product_id, source_variant_id)

inventory_snapshots
  id UUID PK
  tenant_id UUID
  integration_id UUID
  variant_id UUID
  source_location_id TEXT NULL
  available_quantity INT
  on_hand_quantity INT NULL
  observed_at TIMESTAMPTZ
```

Cost may be unavailable. Policy must treat unknown cost explicitly.

## 9. Orders and pseudonymous customer facts

```text
customer_facts
  id UUID PK
  tenant_id UUID
  integration_id UUID
  source_customer_hash TEXT
  first_order_at TIMESTAMPTZ NULL
  last_order_at TIMESTAMPTZ NULL
  order_count INT
  lifetime_value_minor BIGINT
  currency CHAR(3)
  created_at TIMESTAMPTZ
  updated_at TIMESTAMPTZ
  UNIQUE (tenant_id, integration_id, source_customer_hash)

orders
  id UUID PK
  tenant_id UUID
  integration_id UUID
  source_order_id TEXT
  customer_fact_id UUID NULL
  created_at TIMESTAMPTZ
  cancelled_at TIMESTAMPTZ NULL
  financial_status TEXT
  subtotal_minor BIGINT
  discount_minor BIGINT
  refund_minor BIGINT
  tax_minor BIGINT
  shipping_minor BIGINT
  total_minor BIGINT
  currency CHAR(3)
  is_first_order BOOLEAN NULL
  source_channel TEXT NULL
  content_hash TEXT
  source_updated_at TIMESTAMPTZ
  UNIQUE (tenant_id, integration_id, source_order_id)

order_lines
  id UUID PK
  tenant_id UUID
  order_id UUID
  product_id UUID NULL
  variant_id UUID NULL
  quantity INT
  unit_price_minor BIGINT
  discount_minor BIGINT
  refund_minor BIGINT
  cost_minor BIGINT NULL
```

Do not persist customer names, raw email, phone, address, order notes, or payment details in the MVP.

## 10. Behavioral events

```text
behavioral_events
  id UUID PK
  tenant_id UUID
  integration_id UUID NULL
  source TEXT
  source_event_id TEXT
  schema_version TEXT
  event_type TEXT
  occurred_at TIMESTAMPTZ
  received_at TIMESTAMPTZ
  session_id_hash TEXT
  anonymous_user_id_hash TEXT NULL
  product_id UUID NULL
  variant_id UUID NULL
  query_id UUID NULL
  result_position INT NULL
  surface TEXT
  consent JSONB
  safe_properties JSONB
  UNIQUE (tenant_id, source, source_event_id)
```

Partition later when volume requires it.

## 11. Search metadata

```text
search_index_versions
  id UUID PK
  tenant_id UUID
  name TEXT
  embedding_model TEXT
  sparse_model TEXT
  document_template_version TEXT
  ranking_version TEXT
  status TEXT
  indexed_product_count INT
  created_at TIMESTAMPTZ
  activated_at TIMESTAMPTZ NULL

search_boost_rules
  id UUID PK
  tenant_id UUID
  query_pattern JSONB
  product_scope JSONB
  multiplier NUMERIC
  starts_at TIMESTAMPTZ
  ends_at TIMESTAMPTZ
  action_id UUID
  status TEXT
  version INT
```

Qdrant points are reconstructable and do not replace these records.

## 12. Goals, policies, and runs

```text
goals
  id UUID PK
  tenant_id UUID
  name TEXT
  objective JSONB
  horizon JSONB
  autonomy JSONB
  allowed_action_types TEXT[]
  evaluation_schedule JSONB
  status TEXT
  policy_version_id UUID
  created_at TIMESTAMPTZ
  updated_at TIMESTAMPTZ
  version INT

goal_budgets
  id UUID PK
  tenant_id UUID
  goal_id UUID
  kind TEXT
  allocated_minor BIGINT
  currency CHAR(3)
  period_start TIMESTAMPTZ
  period_end TIMESTAMPTZ
  UNIQUE (goal_id, kind, period_start)

goal_constraints
  id UUID PK
  tenant_id UUID
  goal_id UUID
  metric TEXT
  operator TEXT
  value JSONB
  hard BOOLEAN
  created_at TIMESTAMPTZ

policy_versions
  id UUID PK
  tenant_id UUID
  scope_type TEXT
  scope_id UUID NULL
  version INT
  policy JSONB
  content_hash TEXT
  created_by UUID
  created_at TIMESTAMPTZ
```

Run tables:

```text
goal_runs
  id UUID PK
  tenant_id UUID
  goal_id UUID
  thread_id TEXT
  trigger TEXT
  status TEXT
  observation_snapshot_id UUID NULL
  policy_version_id UUID
  started_at TIMESTAMPTZ
  completed_at TIMESTAMPTZ NULL
  error_code TEXT NULL
  safe_error JSONB NULL
  UNIQUE (tenant_id, goal_id, thread_id)

goal_run_steps
  id UUID PK
  tenant_id UUID
  run_id UUID
  sequence INT
  node_name TEXT
  status TEXT
  input_refs JSONB
  output_refs JSONB
  trace_id TEXT
  started_at TIMESTAMPTZ
  completed_at TIMESTAMPTZ NULL
  UNIQUE (run_id, sequence)
```

Store LangGraph checkpoint tables according to the checkpointer package, separately from domain records.

## 13. Snapshots, opportunities, and actions

```text
observation_snapshots
  id UUID PK
  tenant_id UUID
  goal_id UUID
  as_of TIMESTAMPTZ
  data JSONB
  content_hash TEXT
  created_at TIMESTAMPTZ

opportunities
  id UUID PK
  tenant_id UUID
  goal_id UUID
  snapshot_id UUID
  type TEXT
  entity_refs JSONB
  evidence JSONB
  estimated_value_minor BIGINT NULL
  currency CHAR(3) NULL
  confidence NUMERIC
  detector_code TEXT
  status TEXT
  created_at TIMESTAMPTZ
  expires_at TIMESTAMPTZ NULL

action_intents
  id UUID PK
  tenant_id UUID
  goal_id UUID
  run_id UUID
  type TEXT
  payload JSONB
  rationale TEXT
  opportunity_ids UUID[]
  actor JSONB
  created_at TIMESTAMPTZ

compiled_actions
  id UUID PK
  tenant_id UUID
  goal_id UUID
  run_id UUID
  intent_id UUID
  type TEXT
  target_provider JSONB
  normalized_parameters JSONB
  preconditions JSONB
  expected_impact JSONB
  estimated_cost_minor BIGINT
  currency CHAR(3)
  risk JSONB
  rollback_plan JSONB
  idempotency_key TEXT
  version_hash TEXT
  status TEXT
  expires_at TIMESTAMPTZ
  created_at TIMESTAMPTZ
  updated_at TIMESTAMPTZ
  version INT
  UNIQUE (tenant_id, idempotency_key)
```

## 14. Policy decisions and approvals

```text
policy_decisions
  id UUID PK
  tenant_id UUID
  action_id UUID
  policy_version_id UUID
  action_version_hash TEXT
  outcome TEXT
  reason_codes TEXT[]
  evaluated_rules JSONB
  required_roles TEXT[]
  valid_until TIMESTAMPTZ
  created_at TIMESTAMPTZ

approval_requests
  id UUID PK
  tenant_id UUID
  action_id UUID
  action_version_hash TEXT
  required_roles TEXT[]
  status TEXT
  expires_at TIMESTAMPTZ
  created_at TIMESTAMPTZ

approvals
  id UUID PK
  tenant_id UUID
  request_id UUID
  actor_user_id UUID
  decision TEXT
  comment TEXT NULL
  action_version_hash TEXT
  decided_at TIMESTAMPTZ
  UNIQUE (request_id, actor_user_id)
```

Any action mutation changes the hash and invalidates prior approval.

## 15. Execution, reconciliation, and outcomes

```text
action_executions
  id UUID PK
  tenant_id UUID
  action_id UUID
  integration_id UUID
  attempt INT
  status TEXT
  request_summary JSONB
  response_summary JSONB NULL
  provider_request_id TEXT NULL
  provider_resource_id TEXT NULL
  before_state JSONB
  after_state JSONB NULL
  started_at TIMESTAMPTZ
  completed_at TIMESTAMPTZ NULL
  error_code TEXT NULL
  UNIQUE (action_id, attempt)

action_reconciliations
  id UUID PK
  tenant_id UUID
  execution_id UUID
  observed_remote_state JSONB
  outcome TEXT
  reconciled_at TIMESTAMPTZ
  details JSONB

interventions
  id UUID PK
  tenant_id UUID
  action_id UUID
  starts_at TIMESTAMPTZ
  ends_at TIMESTAMPTZ NULL
  primary_metric TEXT
  monitor_spec JSONB
  status TEXT

intervention_outcomes
  id UUID PK
  tenant_id UUID
  intervention_id UUID
  evaluated_at TIMESTAMPTZ
  metric_results JSONB
  method TEXT
  sample_size INT NULL
  conclusion TEXT
  guardrail_status TEXT
```

## 16. Budget ledger

```text
budget_accounts
  id UUID PK
  tenant_id UUID
  goal_id UUID
  budget_kind TEXT
  currency CHAR(3)
  allocated_minor BIGINT
  period_start TIMESTAMPTZ
  period_end TIMESTAMPTZ
  version INT
  UNIQUE (goal_id, budget_kind, period_start)

budget_ledger_entries
  id UUID PK
  tenant_id UUID
  account_id UUID
  action_id UUID NULL
  operation_id TEXT
  entry_type TEXT
  amount_minor BIGINT
  metadata JSONB
  created_at TIMESTAMPTZ
  UNIQUE (account_id, operation_id)
```

Balances are derived transactionally:

```text
available
= allocated
- active reservations
- committed
+ releases/adjustments
```

Lock the account row or use an equivalent serializable reservation strategy.

## 17. Audit, webhooks, and sync

```text
audit_events
  id UUID PK
  tenant_id UUID
  actor JSONB
  event_type TEXT
  entity_type TEXT
  entity_id UUID
  request_id TEXT
  run_id UUID NULL
  safe_payload JSONB
  previous_event_hash TEXT NULL
  event_hash TEXT NULL
  occurred_at TIMESTAMPTZ

webhook_receipts
  id UUID PK
  tenant_id UUID NULL
  integration_id UUID NULL
  provider TEXT
  source_event_id TEXT
  topic TEXT
  signature_valid BOOLEAN
  status TEXT
  payload_hash TEXT
  received_at TIMESTAMPTZ
  processed_at TIMESTAMPTZ NULL
  error_code TEXT NULL
  UNIQUE (provider, source_event_id)

sync_jobs
  id UUID PK
  tenant_id UUID
  integration_id UUID
  resource_type TEXT
  mode TEXT
  status TEXT
  source_cursor TEXT NULL
  high_watermark TIMESTAMPTZ NULL
  source_count BIGINT NULL
  normalized_count BIGINT NULL
  started_at TIMESTAMPTZ
  completed_at TIMESTAMPTZ NULL
  safe_error JSONB NULL

source_mappings
  id UUID PK
  tenant_id UUID
  integration_id UUID
  entity_type TEXT
  source_id TEXT
  normalized_id UUID
  source_updated_at TIMESTAMPTZ NULL
  source_payload_hash TEXT NULL
  UNIQUE (tenant_id, integration_id, entity_type, source_id)
```

Application roles must not update/delete audit rows.

## 18. Indexes and constraints

At minimum:

- products `(tenant_id, integration_id, source_updated_at)`;
- variants `(tenant_id, product_id, sku)`;
- inventory `(tenant_id, variant_id, observed_at desc)`;
- orders `(tenant_id, created_at desc)`;
- orders `(tenant_id, customer_fact_id, created_at)`;
- events `(tenant_id, event_type, occurred_at desc)`;
- goals partial index on active;
- runs `(tenant_id, goal_id, started_at desc)`;
- actions partial index on awaiting approval/executable/uncertain;
- executions partial index on unreconciled;
- webhooks partial index on pending/failed;
- sync jobs `(tenant_id, integration_id, resource_type, started_at desc)`.

Foreign-key relationships must not allow a tenant-owned child to point to another tenant. Use composite constraints where practical and repository assertions everywhere.

## 19. Idempotency and canonical hashes

Canonical JSON:

- sorted keys;
- normalized enum strings;
- decimals serialized canonically;
- UTC timestamps;
- no volatile fields.

Action key:

```text
sha256(
  tenant_id
  + goal_id
  + action_type
  + target_provider
  + canonical_parameters
  + target_resource_versions
  + logical_decision_window
)
```

Webhook key uses provider event ID/topic/account. Behavioral event uses source event ID.

## 20. Freshness

Store freshness by integration/resource:

- catalog;
- inventory;
- orders;
- discounts;
- behavioral events;
- campaigns/spend.

A snapshot records the exact freshness used. Policy evaluates it before every material action.

## 21. Retention and deletion

Deletion workflow:

1. disable integration and schedules;
2. revoke/delete credentials;
3. remove Qdrant points;
4. delete/anonymize customer-linked facts/events;
5. delete provider payload artifacts;
6. retain only permitted minimal audit metadata;
7. record completion without retaining deleted content.

## 22. Database acceptance criteria

- empty database migrates cleanly;
- models round-trip;
- money/currency constraints hold;
- state transitions are enforced by service and tested;
- concurrent budget reservations never exceed allocation;
- action idempotency is unique per tenant;
- approval hash invalidation works;
- all repository queries require tenant scope;
- audit rows are append-only;
- Qdrant can be rebuilt from catalog tables;
- deletion removes indexed and credential data.
