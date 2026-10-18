# Contributing

This is private pre-launch development after the frozen simulator RC. First-party
code and accepted contributions use [Apache-2.0](LICENSE). Contributors retain
copyright in their own contributions; contributions are not assigned to Han Chen.

## Developer Certificate of Origin

Every contributed commit must certify [DCO 1.1](DCO.md) with a commit trailer:

```text
Signed-off-by: Full Name <email@example.com>
```

Use your own name and email matching the commit author, and create the trailer with:

```bash
git commit -s
```

Each coauthor must supply their own matching sign-off. Do not sign on someone
else's behalf. The DCO certifies contribution rights and does not transfer
copyright ownership. There is no CLA, copyright assignment or proprietary
relicensing agreement. The repository owner follows the same policy after public
launch. Existing private development history is not retroactively certified.

The `DCO / DCO` pull-request check verifies every contributed commit, including
merge commits, against the PR base. Configure it as a required status check in
branch protection or repository rulesets before accepting public pull requests;
do not allow maintainer bypasses. Squashing does not excuse unsigned input commits.
Required-check configuration and its verified hosted state are recorded in the
release report; a workflow file alone does not enforce branch protection.
The checker validates trailers, not the truth of a contributor's legal certification.

## Setup and validation

The [README](README.md) quickstart runs the self-hosted application. For development,
use Python 3.12+, Node 22, the pinned uv/pnpm tooling and committed lockfiles. Point
integration tests at dedicated disposable PostgreSQL, Redis and Qdrant services,
not your store. The tests create their own databases and fixture state.

```bash
make bootstrap
make check
make test-integration
make install-browser
```

Run the isolated self-service browser command in the
[first-store reproduction guide](docs/FIRST_STORE_DEMO.md#reproduce) for the alpha
owner/shopper smoke test. It starts its own API, worker and clients, exercises a
real disposable database, and retains screenshots in your chosen fresh output
directory. It does not use your signed-in browser or reset your existing store.

`make test-e2e` includes legacy simulator suites and is not the smoke command for
the default self-hosted profile. Run it only against a dedicated `legacy_demo`
fixture with matching `PLAYWRIGHT_BASE_URL` and test dependency URLs. Never switch
an existing authenticated store to legacy mode to make a test pass. Outage tests
deliberately stop services; run them only in a dedicated project.

Use `.next` or a `.next-*` directory for isolated client build output through
`OPEN_COMMERCE_NEXT_DIST_DIR`. Git, Docker and lint exclude these generated
directories; keep application source outside them. Next may update `next-env.d.ts`
and the type includes in `tsconfig.json` when switching output directories.
Review those generated changes before freezing a source snapshot, and validate
the exported copy rather than assuming a running preview matches its bytes.

## Changes

Read `AGENTS.md`, `PLANS.md`, the [canonical architecture](docs/ARCHITECTURE.md)
and [extension guide](docs/EXTENDING.md) first. Work affecting
more than three files needs an execution plan. Preserve unrelated work.

- Keep domain/policy code independent of HTTP, UI and external-provider packages.
- Put provider behavior behind typed interfaces. The executor is the only
  consequential write path; models and natural-language drafts are untrusted inputs.
- Scope tenant-owned queries, preserve approvals/idempotency/audit/rollback checks,
  and never add inventory-quantity writes or a live connector in this release.
- Add regressions for behavior changes, especially failure, restart and race paths.
- Do not replace database durability tests with in-memory repositories.
- Regenerate OpenAPI and SDK together, then check their freshness and compilation.
- Keep benchmark inputs and unfavorable rows. Record version changes that affect
  deterministic output; do not update golden files simply to make tests green.
- Document verified behavior and residual risk. No unmeasured safety or lift claims.

Run the narrowest relevant checks during development and full gates before review.
Start a branch from current `main`; never edit or retag the frozen release candidate.
Current private owner commits use the authorized owner identity and `git commit -s`.
Other contributors must use their own identity, never copy an owner's sign-off.
The [development CI proposal](docs/CI_DEVELOPMENT.md) preserves all existing required
qualification contexts. A passed workflow does not substitute for a required review.
For release evaluation, `make controller-eval` is the full 100-seed sweep;
`make controller-eval-smoke` is only a fast regression. See the
[evaluation methodology](docs/benchmarks/controller-v2.md).

## Review and release

Review the full diff, relevant contracts, tests and migrations before changing
code. Check correctness, tenant authorization and privacy, typed tool admission,
approval and idempotency boundaries, failure recovery, and truthful product and
measurement claims. Include boundary, restart and concurrent-request cases;
passing mocks alone do not establish working persistence or browser behavior.

Return findings first, ordered BLOCKER, HIGH, MEDIUM, LOW. Each finding needs an
exact code location, reproducible failure, impact, minimal correction and a
regression test. Record checks run, checks omitted with reasons, and remaining
limitations. Recommend MERGE, MERGE AFTER FIXES or DO NOT MERGE; do not claim a
check passed unless it actually ran against the reviewed source.

Resolve BLOCKER/HIGH findings before qualification. The owner approves legal
terms, tags and publication; contributors and automation must not publish
artifacts on their behalf. Private development prompts and review transcripts
are not prerequisites for contributing to the public source snapshot.
