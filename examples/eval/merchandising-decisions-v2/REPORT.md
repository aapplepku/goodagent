# Merchandising decisions v2

Private deterministic simulator evaluation. Not real-model validation, merchant
lift, production approval or release qualification. The registered held-out run
completed all 36 arms from clean pre-outcome commit
`e11c226f60b0d1895726ae20887a6044a4d4f948`; runtime and protocol remain frozen.
All raw/source/setup checks pass, with no outcome-driven tuning.

- [Original hosted failure and independent reproduction](hosted/DIAGNOSIS.md).
- [Why v1 selected 34 prices, two promotions and no search/PDP](V1_DIAGNOSIS.md).
- [Registered protocol](protocol.md) and [pre-outcome horizon amendment](protocol-amendment-1.md).
- [Decision rules and safety boundaries](../../../docs/MERCHANDISING_DECISIONS.md).
- [Retained development failures and three-arm results](DEVELOPMENT_FINDINGS.md).
- [Complete held-out results, uncertainty and adverse trajectories](HELD_OUT_FINDINGS.md).
- [Candidate-level trajectory guide](TRAJECTORIES.md).
- [Local, hosted, browser and worker-health validation limits](VALIDATION.md).

The twelve-arm development comparison completed with matched setup/permission
hashes and incoming sessions, no controller errors and no recorded hard-policy
violations. Revised profit is lower in all three longer conditions. Actual
controller-selected price experiments and PDP replanning are demonstrated;
search/new-promotion selection and observed-stop selection are not demonstrated
there. Authored tests cover those decision/path boundaries separately.

Use `results/development-three-arm/summary-reviewed.json.gz`; its manifest binds
every raw trajectory and original source snapshot. The older summary remains as a
documented reporting diagnostic, not the authoritative repeat count. Late
measurements remain pending. No favorable outcome is required for acceptance.

Held-out: revised selects 23 PDP and 25 price actions, without repeated price
targets within an arm, with
96/144 waits; v1 executes 16 prices and seven promotions, with 121/144 days
without execution including six denied proposals. All four mean revised/v1
profit differences are positive, but every descriptive profit interval contains
zero and three of twelve pairs are adverse. No search boost, new promotion or
explicit stop is selected by revised. Eleven PDP adjustments occur at expected
version two. Half its 48 measurements remain pending. No controller errors,
recorded hard-policy/economic guardrail violations or model calls occur.
These findings demonstrate bounded inspectability, not reliable profit lift.

## Reproduction

These are historical evaluation instructions. The public export does not include
the original private Git history or hosted artifact ZIPs. In particular, the
exact held-out reproduction below requires private prerequisites unavailable in
this snapshot; inspecting its retained result files is not reproducing that run.

Use an isolated local PostgreSQL server with database-create permission, Redis,
Qdrant and the checksum-verified pinned MiniLM installation. Set
`OPEN_COMMERCE_TEST_ADMIN_DATABASE_URL`, `OPEN_COMMERCE_REDIS_URL` and
`OPEN_COMMERCE_QDRANT_URL` to those local services. The runner creates and removes
only its uniquely named evaluation database. Existing business/demo data is not
reset. Model planning stays disabled.

```bash
uv run python -m scripts.run_merchandising_decisions \
  --split development --model-directory .opencommerce/merchandising/models/minilm \
  --output .opencommerce/decisions-development-reproduction
uv run python -m scripts.summarize_merchandising_decisions \
  .opencommerce/decisions-development-reproduction \
  --output .opencommerce/decisions-development-summary.json.gz --require-complete
```

Held-out requires `--split held_out --frozen-commit <full-pre-outcome-SHA>` and a
clean checkout exactly at that SHA. Never overwrite earlier outputs. A repeated
run is a reproduction/regression, not a new independent case. The runner retains
partial failures and stops mixing versions if source changes during execution.

Final local `make check` passes: strict typing covers 278 Python files; 514
backend/contracts, eight SDK and 71 web tests pass; 77 real-service integrations
pass with one explicitly gated real-model skip. Exact-image/source security
review passes without relaxing the gate. The corrected merchandising browser
workflow passes, but four other browser workflows and the worker's five-second
health deadline remain unverified under local resource pressure. Private draft
PR #4 is stacked on the exact merchandising base. Its first hosted run stopped
before source checkout and skipped qualification; no hosted code-validation pass
is claimed. Account-specific provider annotations remain private. Details are in
VALIDATION.md and the [sanitized execution summary](validation/hosted-public-summary.json).
