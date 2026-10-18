# Durable Controller Evaluation

The historical three-seed proposals-only check is not release evidence and has
been removed. The replacement uses a freshly migrated PostgreSQL database and
the deployed durable controller, executor and worker nodes.

## Run and reproduce

With local PostgreSQL running and the host database URL configured:

```bash
make controller-eval
```

This runs seeds 0 through 99, all three built-in scenarios, standard goals and
physical-inventory-infeasible variants, and two arms per case: no intervention
and the goal-conditioned controller. Each arm covers 30 virtual days. The output
is `examples/eval/results/controller-v2-durable.json.gz`, with raw rows, daily
metrics, dispatch checks, outcomes, ledger summaries and distribution statistics.
An interrupted run leaves an ignored partial JSONL journal, not a qualified result.

```bash
uv run commerce-agent controller evaluate \
  --verify examples/eval/results/controller-v2-durable.json.gz \
  --output /tmp/controller-reproduction.json.gz
```

Verification compares all non-timing evidence, not just favorable summary fields.
Each run uses and removes only its own random `opencommerce_bench_*` database.
It requires local credentials allowed to create a scratch database. It does not
delete the configured demo database or use an in-memory repository for execution.
Do not stop PostgreSQL while the sweep runs. This is a substantial local computation.

`make controller-eval-smoke` runs only seed 42 for three days and compares the
committed smoke artifact. It tests the harness but does **not** satisfy the seed
or horizon release requirement. Its artifact reproduced across separate processes
and serial/concurrent case scheduling during qualification.

## Methods and interpretation

- Both arms use identical seeded catalogs, total/daily spend limits and horizons.
  The no-intervention arm retains scenario-provided campaigns but makes no controller writes.
- A simulated owner/operator approves exact pending hashes. This evaluates an
  approval-assisted controller, not unattended autonomy or human decision quality.
- Ordinary JobRunner measurement nodes run after each virtual day. Only delivery
  backoff is accelerated; policy gates, measurements, budget writes and pauses are
  not bypassed. No automatic unpause or speculative rollback is added for the benchmark.
- There is no separate fixed-rule baseline implementation. The planner itself is
  deterministic and goal-conditioned; no additional baseline performance is invented.
- Standard scenario count targets are 200. Some are already on track and legitimately
  execute no action. The raw action count makes this visible; those rows cannot
  establish safety of an action path that was not exercised.
- Infeasible targets exceed the generated scoped physical inventory bound by one.
  Baseline feasibility values are read-only assessment results, not baseline planning.
- Hard violations inspect dispatch gates, actual unique receipts/reconciliation,
  total/daily spend and ledger invariants. Aggregate observed CAC/margin breaches
  are reported separately and can pause planning. Zero hard violations does not mean
  every economic goal or outcome guardrail was met.
- Objective outcomes, CAC in minor units, contribution margin/profit, spending,
  actions, rollbacks, hard violations and observed breaches include mean, population
  standard deviation and linearly interpolated p10/p50/p90. Undefined CAC stays null
  and is excluded with an explicit missing count.
- No benchmark row or unfavorable result is removed. An execution failure stops
  qualification and is retained as a failing case. No tuning against a favorable
  subset or causal/merchant-lift claim is supported by this synthetic engine.

The full sweep has produced the [generated result tables](controller-v2-results.md).
They are rendered from validated raw evidence, not manually entered measurements:

```bash
.venv/bin/python scripts/render-controller-report.py
```

Independent full reproduction passed on September 5, 2026. The
[original artifact](../../examples/eval/results/controller-v2-durable.json.gz)
and [independent artifact](../../examples/eval/results/controller-v2-durable-reproduction.json.gz)
have identical 1,200 non-timing rows and summaries, no failed cases, and zero
hard-policy violations. Both evidence hashes are
`sha256:a1aeb60320deb3a202a6bc00ac1397f25a0d8b3a59bd2c74ecbe2cd321328e76`.
Elapsed times were 9190.011s and 8723.341s; timing and source/environment metadata
are retained separately, not required to be identical. The full renderer validated
both raw artifacts, coverage and recomputed summaries. Consult
[implementation status](../IMPLEMENTATION_STATUS.md) for exact commands and source
boundaries; this synthetic result is not release approval.
