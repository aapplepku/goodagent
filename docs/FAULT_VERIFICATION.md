# Restart and Fault Verification

These tests use real PostgreSQL transactions. Process-failure tests use actual
OS processes; availability drills stop and restart the explicitly named Compose
services. No in-memory repository stands in for durability or concurrency.
The simulator's effect and receipt commit together in PostgreSQL. These results
do not establish the behavior of a future remote commerce provider.

## Required matrix

Test names below are executable evidence locators, not independent certifications.

| # | Required case | Test and asserted recovery |
| --- | --- | --- |
| 1 | Active-goal API restart | `tests/integration/test_process_recovery.py::test_active_goal_approval_and_sse_survive_actual_api_process_restart`: goal, pending action, approval hash and trace survive process termination. |
| 2 | Worker restart before execution | `test_process_recovery.py::test_worker_process_dies_and_restarted_worker_replays_only_durable_ids[leased]`: exit 85 after durable lease, restarted runner completes the same job exactly once. |
| 3 | Worker dies after provider success | Same test, `[provider_committed]`: exit 86 after committed simulator effect, one receipt and one execution attempt remain after recovery. |
| 4 | Approval interrupt and API restart | Active-goal process test restarts first with a pending approval request, then again after saving the approval decision while the worker is stopped. It checks the same approval ID/hash before starting the worker to resume the original run. The strengthened test passed in targeted, root full-suite and clean-clone full-suite runs. |
| 5 | Concurrent identical API requests | `tests/integration/test_durable_api_worker.py::test_default_api_delivers_durable_run_through_real_redis_worker`: four concurrent HTTP requests return one goal ID; same-key changed payload returns 409. `test_durable_storage.py::test_concurrent_duplicate_requests_mutate_only_once` separately races independent pools and proves one simulator mutation. |
| 6 | Duplicate worker delivery | `tests/integration/test_durable_controller.py::test_duplicate_delivery_and_double_rollback_are_idempotent` and process-recovery tests: repeated delivery cannot create a second effect. |
| 7 | Budget reservation race | `tests/integration/test_durable_safety.py::test_budget_reservation_race_and_overrelease[goal/daily]`: independent pools exercise the ledger lock without relying on the tenant advisory lock; only one 70-unit reservation can consume a 100-unit balance. |
| 8 | Kill switch between approval and execution | `test_durable_safety.py::test_changes_after_approval_block_provider_write[kill]` and `test_kill_after_preparation_releases_reservation_without_effect`: dispatch is blocked and unused reservations released. |
| 9 | Target changes after approval | `test_changes_after_approval_block_provider_write[target]`: authoritative campaign change blocks dispatch, with no provider receipt. |
| 10 | Policy changes after approval | Same test, `[policy]`: approval bound to the old policy version cannot authorize a new dispatch. |
| 11 | Action becomes stale | Same test, `[expiry]`, plus `tests/integration/test_durable_cycles.py::test_expired_approval_cannot_stall_next_virtual_day`: expiry blocks the write without permanently stalling planning. |
| 12 | Temporary Redis outage | `tests/fault/test_compose_outages.py::test_redis_outage_retains_approved_work_and_resumes_without_api_retry`: readiness fails, liveness remains, approved work persists, worker recovers from PostgreSQL without an API retry. |
| 13 | Temporary Qdrant outage | `test_qdrant_outage_fails_closed_then_reuses_durable_catalog`: safe 503 without a local retrieval fallback, then identical catalog-backed result after restart. |
| 14 | PostgreSQL restart | `test_postgres_restart_retains_goal_approval_and_trace`: safe unavailable response during outage; saved goal, trace and approval recover afterward. |
| 15 | SSE disconnect and resume | API process and container tests: a new connection using `Last-Event-ID` receives unique events strictly after the stored cursor. This API returns bounded event snapshots, not an indefinitely open push connection. |
| 16 | Rollback requested twice | Durable duplicate-delivery test: repeated rollback returns the existing result and restores the target once. |
| 17 | Ambiguous response | `test_durable_safety.py::test_ambiguous_execution_reconciles_before_retry`: interruption after effect plus divergent target remains `uncertain`; same-key and new-key retries do not create another provider effect. |

Unqualified short paths in the table are in `tests/integration/`, except where
the preceding row identifies `tests/fault/` explicitly.

## Recorded runs

On September 5, the complete real-service integration suite passed **40 tests in
129.35 seconds**, including the subprocess exits and independent-pool races. The
four Compose outage drills passed in **47.58 seconds** against an isolated
disposable Compose project.
Runtime version/image details are in [implementation status](IMPLEMENTATION_STATUS.md)
and [security evidence](SECURITY_VERIFICATION.md). Subsequent code changes require
the complete suite to run again before release qualification is complete.

The independent second clean clone
then passed `make check` including **40 integration tests in 222.56s**, explicit
`make test-integration` with **40 passed in 180.35s**, and `make test-fault` with
**4 passed in 42.96s**. All three named volumes of that disposable project were
then deleted; startup recreated them, applied all five migrations, returned an
empty goal list and passed both production browser cases (**1.1m**).
Subsequent archive/HTTP/browser corrections require the next source/image checkpoint.

Final clean-v4 includes those corrections and passed `make check` with **41
integration tests in 249.30s**, explicit `make test-integration` with **41 passed
in 259.38s**, and all **4 fault tests in 55.72s**. Production browser tests passed
before reset (**3 in 1.5m**). Exactly clean-v4's three named volumes were removed;
all five migrations applied from empty again, the goal list was empty, all six
running services became healthy and post-reset browser tests passed (**3 in 1.6m**).
No benchmark database or unrelated project was stopped or reset.

```bash
make test-integration
COMPOSE_PROJECT_NAME=opencommerce-<disposable-project> make test-fault
```

Configure the dependency URLs and Compose port variables for that same project.
Never run availability drills against a stack used for a benchmark or ordinary
work. The fault command requires explicit opt-in through its Make target and a
project name beginning `opencommerce-`; it does not delete volumes.

## Additional boundaries

- The policy unit suite tests malformed/injected drafts, unsupported capability,
  approval hash, price/discount/budget/margin/inventory/freshness limits and both
  tenant/integration kill switches. It is not a substitute for the database races.
- The parallel-intervention limit has a separate two-pool race/restart regression.
- Measurement polling and repeated actual failures have separate restart tests;
  healthy polling does not consume the worker's failure budget.
- Production browser tests exercise acquisition, approval, search, reseeding,
  persisted selection/history and delayed-read handling. They do not replace the
  process-kill tests and do not assert live-provider functionality.
