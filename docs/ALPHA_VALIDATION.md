# Alpha validation status

As of October 19, 2026 UTC. **Not a release approval.** No public repository, release,
package or container publication is implied by this document. This is a sanitized
summary; private review transcripts, credentials and account data are not included.

## Current Reading Guide

### Catalog, Checkout And Preview Follow-Up

A stable local run ending October 19 at 02:12 UTC passed lint, type checking,
generated OpenAPI/client freshness, **4,134 Python cases, 245 integration cases
and 624 frontend/SDK cases**. Python retained three host permission-bit skips and
five failures: four genuine qualification failures (runtime dependency notices, expired
build assessments, deployment/source mismatch and expired optional-runtime
assessments), plus a recorder-source contract still pinned to the old preview
entry. The reviewed entry-only change updates that strict pin; model calls and
acceptance assertions remain unchanged. Integration retained 11 opt-in skips.
No security/attribution gate was waived.
All 1,833 selected records stayed unchanged during that run, with source tree
`8470d79a1a70441afdad3e1ff714fb9fa4df2eadf6dfb225766ae4932ad4af6e`.

Both native browser/cache checks passed. They include one owner-to-guest journey,
legacy sign-in rendering and the warm image-cache rejection check, not two fresh
complete store journeys. Selected desktop/mobile frames were inspected for
catalog thumbnail continuity and the supplied checkout deadline. The fixture uses
synthetic products/images and Basic mode, not real-model conversation evidence.

Scoped fixes prevent unchanged catalog images from being reset on rerender,
recover replacement images after a failure, show the server's actual checkout
hold deadline, and open authorized private previews directly at chat without
automatically sending or marking search tested. Public shoppers still browse
first. Independent source/PM review and regression tests cover those changes.

A later narrow cart hardening forwards the authenticated account-data version
and rechecks it inside the write transaction before replay or mutation. This
fences already-admitted commands after deletion or expiry; it is not a complete
cart-retry protocol. An ambiguous Add after a lost response can still become a
new intent, and reload-safe original-intent recovery remains open. See
[cart authority and limits](CART_CHECKOUT.md). The later backend/test and recorder
corrections are not silently included in the earlier tested source identity above.

The updated collection preflight supports explicitly pinned, bounded linear
follow-ups to the history-free export while retaining the default single-commit
rule. Local tests and actual-candidate preflight passed, but independent CI review,
protected adoption and hosted execution remain unfinished. Fresh exact-artifact
security/attribution review, installation/recovery qualification, model acceptance,
the two real-model recordings and final owner approval remain separate gates.

### CI Diagnostic Privacy Hardening

The October 18 run ending at 23:14 UTC passed lint, type checking, generated
OpenAPI/client freshness, **4,113 Python cases, 245 integration cases, 608
frontend/SDK cases and both browser journeys**. One Python case and 11 opt-in
integration cases were skipped. `make test` remains nonzero for the same four
qualification gates: runtime dependency attribution, expired build assessments,
current-deployment evidence mismatch and expired optional-runtime assessments.
No gate was waived. All 1,833 selected records stayed unchanged during the run,
with source tree `93a7d107d9de7bbe6202b66d0c84064ec822a0a9732e47c0f7054af623315fa3`.

Scoped independent review covered diagnostic staging, upload conditions, bounded
gzip decoding and receipt verification. Actual cached, network-disabled secret
scanner fixtures accepted clean diagnostics and the narrowly allowed public GPG
fingerprint, while rejecting synthetic secrets in image and compressed reports.
Metadata-bearing, concatenated, malformed and oversized gzip input is rejected;
binary browser traces/media require separate review. This is not a current
vulnerability collection, PII guarantee, hosted run or security qualification.

The initial development attempt exposed test-only typing and stale upload-path
assertions; its failures remain retained and are not counted as the stable result.
This reading-guide update follows stable validation and changes documentation
only. The final exported tree must receive fresh hash/content/link review; the
earlier run is not silently relabeled as a rerun of later documentation bytes.

### Source-Only Packaging Validation

The run ending October 18 at 21:44 UTC passed lint, type checking, OpenAPI/client
freshness, **4,089 Python cases, 245 integration cases, 608 frontend/SDK cases and
both browser journeys**. One Python case and 11 opt-in integration cases were
skipped. Four release gates still failed: dependency-runtime attribution, expired
build-dependency assessments, current-deployment evidence mismatch and expired
optional-runtime assessments. No gate was waived or risk acceptance extended.
All 1,830 selected records stayed unchanged during the run, with source tree
`73d6edf1a6860ab751fe33b77069553fbe6f3e928bf9e54dd129d6209e77a507`.

A separate exported-copy rehearsal ended at 21:41 UTC against that same tree.
It reported 4,026 Python passes, five skips, the same four failures and 608
frontend/SDK passes. Lint, formatting, Python/TypeScript types, OpenAPI/client
freshness, canonical legal copies and release-path checks passed. Networking was
denied and no model credentials were inherited. The copy reused installed Python
dependencies and 373 offline cached Node packages with scripts disabled; it was
not a cold Linux/container installation. It excluded private review-tool cases and
retained the four additional host permission-bit skips described below.

Independent scoped review verified removal of 78 affected copied files, exact
derivative hashes, unchanged surviving bytes, re-export idempotence, tamper
rejection and unchanged runtime-attribution failure. The actual frontend notice
collector consumed the derived collection in offline fixtures. Full payload
inspection and an offline directory secret scan were recorded separately; raw
historical scan reports and their limitations remain unchanged. No new Docker
build, vulnerability collection, paid model run or hosted CI was performed.

The final update to this reading guide and README follows those runs. It changes
documentation only; its new export identity requires final content/hash review
and does not retroactively replace the tested tree above.

The subsequent Plan 151 run ended October 18 at 21:06 UTC with **4,079 Python
passes, one skip and four failed release gates**. The additional failure is the
explicit dependency-runtime attribution gate for four missing upstream notices;
the other three security gates remain unchanged. Lint, types, OpenAPI, 245
integration cases (11 opt-in skips), 608 frontend/SDK cases and both browser
journeys passed. All 1,828 then-selected records stayed unchanged during that run.
That run precedes the source-only packaging changes and does not qualify their
exact artifact bytes.

The later source-only export excludes 78 affected copied files from three exact
notice archives, retaining package identities, original hashes and seven
first-party exclusion records. Original private evidence is unchanged. Source
distribution review is separate from still-failing runtime/image attribution
and security qualification. See [dependency attribution](DEPENDENCY_ATTRIBUTION.md).

The recorded full local run in **Session Lifetime And Preview Recovery** below,
ending October 18 at 17:04 UTC: 4,025 Python passes, one skip and three security-gate
failures; 245 integration passes and 11 skips; 608 frontend/SDK passes; both native
browser checks passed. Lint, types and generated API checks passed. The earlier
container/model evidence describes different source identities, not a newer build.

The later history-free copy rehearsal ended at 17:09 UTC: 3,962 Python passes,
five skips and the same three failures, with 608 frontend/SDK passes. The copy
excludes 59 passing private-tool cases and skips four additional permission-bit
cases because the host filesystem clears those bits. Those skips are limitations,
not passing permission coverage. Its selected source hash is
`1ba971e8a9f822dc942b801970f54e234e573b32109ca4b0855f0ed92ac81a93`.
Python dependencies were reused; 373 cached Node packages were installed with zero
downloads and scripts disabled. No fresh Linux, container, integration or browser
run occurred in that copy. Later packaging/documentation edits need their own
inventory; they do not change these recorded results retroactively.

Experimental source disclosure and qualified alpha release are separate decisions.
Unresolved security findings, missing reviews and absent recordings remain visible
even if the owner approves publishing source. See the
[publication checklist](PUBLIC_RELEASE_CHECKLIST.md).

### Resumed Publication Preparation

A repeat full local run from 19:16 to 19:25 UTC on October 18 retained the same
results: 4,025 Python passes, one skip and three security-evidence failures; 245
integration passes and 11 skips; 608 frontend/SDK passes; both native browser
checks passed. Lint, types and generated API checks passed. Selected source stayed
unchanged during the run. Models remained disabled and test stores were isolated.

An offline history-free copy rehearsal starting at 19:19 UTC also retained 3,962
Python passes, five skips, the same three failures and 608 frontend/SDK passes.
Its selected source SHA-256 was
`c8b2f19b68d4e8d44971be4e390dc44b652e067dad646dda928161abbfd1b29f`.
The exclusions, filesystem skips and cached-dependency limitations described above
still apply. This is not hosted CI, a cold Linux install or current-container
qualification. Subsequent CSV export-guard and documentation changes require a new
source identity; these completed runs are not silently rebound to later bytes.

Independent packaging review identified a missing exact-hash approval requirement
for CSVs outside the sample-data directories. This packaging revision requires
approval for every CSV, with explicit hashes for the four already-reviewed downloadable
samples. No sample data is changed. Existing upstream notice omissions remain
disclosed in [legal verification](LEGAL_VERIFICATION.md); this review is not legal
clearance. Future hosted workflow logs/artifacts also require a privacy review
before credentials or additional inputs are introduced.

## What was exercised

| Check | Observed result | Limit |
| --- | --- | --- |
| Fresh macOS developer setup | Dependency installation, lint, type checks and generated-contract checks passed | Not a Linux or production-deployment claim |
| Eight-image Docker build and legal verification | Completed on the private test candidate | Existing build cache allowed; licenses are not a security approval |
| Two fresh production-container journeys | Owner setup through guest shopping passed, with desktop and mobile captures | Deterministic model, two-product fixture without images; not real-model or image-rendering proof |
| Cold backup and isolated restore | Catalog images, search, accounts, memory, demo orders and worker execution preserved | Same machine; not cross-machine disaster recovery |
| Earlier bounded real-model pair | Both failed qualification; 82 requests total, failures retained | Unrelated cards and completion loops motivated revisions |
| Revised bounded real-model pair | Four tests passed in each run; 30 + 29 = 59 requests | Fixed synthetic sample; independent AI evidence review, human narrative approval pending |
| Independent review | Scoped Claude source review and local review/revise/review completed | Supplied source/evidence review, not Claude browser execution; later changes need their own review |
| Corrected import export and local regressions | Recorded runs passed lint/typecheck/OpenAPI, 217 frontend/SDK tests and 133 integration tests; Python/contract had 3,329 passes | 10 integration opt-in skips, one Python skip and three failing historical security gates; not fresh Linux CI qualification |
| Attributed-artwork browser checks | Owner-to-shopper journey, legacy sign-in rendering and warm-cache rejection passed; four welcome/sign-in frames inspected at desktop/mobile sizes | Disposable stores, deterministic provider and no model calls |

The image-cache/artwork source snapshot `c8f6ef88bda91be4f33d756fb731e250b981d3c242dba6eaaf82daa9267ba7d5`
was built at 23:35 UTC on October 17. Two subsequent deterministic production-container
journeys and two native browser/cache tests passed. This is separate from the
earlier real-model pair. Public-export review later found unrelated documents in
that snapshot, so it must remain private. Passing checks are evidence
for their recorded source, not automatically for every later edit. Failed runs
remain retained rather than replaced by successful reruns.
The full suite also retains historical security-gate failures for expired
assessments and source-identity mismatch; those gates have not been weakened.

## Later Local Hardening

Subsequent October 18 source changes are **not included** in the earlier frozen
snapshot or its container/security evidence. Completed local increments cover
unavailable-store recovery, stale shopper/owner account switching, delayed personal
activity after deletion, guest-expiry/registration races, verified store labels,
catalog replacement/retry continuity, and demo-checkout recovery across account
changes, recovery-authentication ordering, owner keyboard controls, safe workspace
retry/reset receipts, bounded provider dispatch and exact catalog-review confirmation.
Shopper welcome now discloses Basic mode before sending, and expired sessions
include verified recovery-code rotation with explicit replacement-code retention.
Store-specific welcome controls now use only authorized catalog thumbnails, with
stable failure placeholders; unrelated sample artwork remains on legacy sign-in,
not inside a merchant's custom store. Ordinary typing does not reset unchanged
thumbnail sources. Independent review reproduced that reset defect before the fix
and verified its closure, including delayed errors after source/account changes.
Each confirmed defect has retained reproduction and scoped regression
evidence; independent local agents reviewed separate authors' changes.

The stable local run ending 12:11 UTC passed lint, type checking and OpenAPI
freshness, 209 integration tests, 545 frontend/SDK tests and two native browser
tests. Python/unit-contract testing reported 3,827 passes, one skip and the same
three historical security-gate failures; integration retained ten opt-in skips.
All 1,807 selected source files stayed unchanged during that run. Both application
production compilations passed with networking denied before the later capture-only
test reorder and gallery updates; product code was unchanged. Desktop/mobile evidence
was inspected for the changed owner identity, catalog recovery and account-recovery
states, including two-tab import recovery and confirmed-reset read failures.
Recovery capture photographs empty forms before entering synthetic credentials.
Actual synthetic image delivery, failed-image controls, private/public asset
authorization and sharing revocation were checked separately; typing an unsent
query caused no repeat request for the observed image. These bounded checks do
not prove every browser/cache behavior or image ingestion quality. Recovery codes are
held in browser memory, not persistent storage, and their receipt is tied to the
verified account. Provider configuration remains distinct from connectivity.
These are deterministic-provider, disposable-store tests, not new model
evaluations, image scans, clean Linux CI or release approval.

Subsequent plan/status documentation records these results separately from the
tested source inventory. No later product change inherits the recorded passes.

### Memory Controls And Current Local Checks

The run ending October 18 at 13:44 UTC covers the later memory-management and
capture-tooling changes: lint, type checking and OpenAPI freshness passed;
3,932 Python/unit-contract tests passed with one skip and the same three historical
security failures; 211 integration tests passed with 11 opt-in skips; 593
frontend/SDK tests and both native browser checks passed. All 1,821 selected files
stayed unchanged. Both apps subsequently compiled with networking denied against
the same source. Later documentation-only updates are separate from that inventory.

Shoppers can inspect and remove retained preferences while saving/recall are off.
An uncertain individual deletion retains its account/store-bound request identity
for explicit retry, including verified same-account session recovery. These retry
receipts are memory-only, not retained across reload. Browser checks exercised an
actual committed deletion whose response was lost, same-key retry, reload, unchanged
cart and 44-pixel mobile controls. Desktop/mobile captures were inspected.
Independent scoped frontend/backend reviews found no further actionable defect;
they do not establish every concurrency or privacy property. The default model
recall/save guards remain separate from authenticated management access.

An additional source-only setup/recovery review passed 107 focused offline cases,
including interrupted backup/restore and explicit-start retries. Docker/file calls
were mocked; this is not a new power-loss or cross-machine recovery demonstration.
No paid model calls, original-store changes, hosted checks or refreshed external
scans were part of these local checks. Historical security gates remain failing.

### Cached Export-Copy Rehearsal

A separate history-free private checkpoint with 1,821 selected files was copied
again for offline execution, with source SHA-256
`452b855e1300db09c906c3a84fd7f3b69330138a0a6555e0a8823d343e2cc197`.
The October 18 run ending at 14:16 UTC verified unchanged selected files in both copies
and package imports from the copy rather than the working repository. Its frozen
Node install reused 373 cached packages with zero downloads; Python dependencies
were reused from the installed local environment. Networking was denied throughout.

Lint/format, Python and frontend type checking, OpenAPI/client freshness, legal
notice consistency, release-path checks and 593 frontend/SDK tests passed. Exported
Python/unit-contract tests reported 3,869 passes, five skips and the same three
historical security failures. Counts differ from the private working repository
because private review tooling is intentionally excluded. Earlier failed rehearsal
attempts remain retained, including missing Node/Python-path harness configuration.
This is not a cold installation, new container build, integration/browser run or
hosted Linux check. Subsequent catalog-status and guest-receipt changes are separate
and do not inherit this checkpoint's results.

### Catalog Status And Retired Guest Receipts

The later run ending October 18 at 14:35 UTC passed lint/type checking/OpenAPI,
227 integration tests (11 opt-in skips), 597 frontend/SDK tests and both native
browser checks. Python tests reported 3,939 passes, one skip and the same three
security-evidence failures. All 1,823 selected files stayed unchanged, source tree
`7368400875e86da42bc30856a1533aab8b06c683cc7cbe8d21f64deeb80b9253`.

Catalog counts now use singular/plural wording and distinguish pending results
from previous results retained after a failed filter. Independent DOM review and
desktop/mobile screenshots cover loading, failure and retry. The fixture uses
synthetic color-block images; this is not product-photo or search-quality evidence.

Guest merge now removes duplicate response copies belonging to the retired guest
without deleting transferred conversations or preferences. Historical cleanup
selects outstanding disabled guests in batches, rechecks eligibility and retains
quota, setting and commerce records. Independent review found the original leak
resolved in bounded probes; actual SQL covers isolation, rollback, registration,
expiry, repeated work and progress past already-cleared accounts. A later test-only
improvement confirms nonempty completed demo orders for both identities and exact
retention after merge and deletion; all 37 focused SQL cases passed again, with an
independent source/type recheck. It does not change production behavior.

Neither updated API nor worker has been deployed to original stores during this
work. Historical repair therefore remains unperformed there. The 100-account batch
does not bound receipt rows or lock duration; backups have independent retention.
No schema, endpoint or credential change is required. The frozen disclosure commit
and old security evidence remain separate from these working-tree changes.

A final pass after the completed-order test improvement ended at 14:47 UTC with
the same results: 3,939 Python passes, one skip and three historical security
failures; 227 integration passes and 11 skips; 597 frontend/SDK passes; both native
checks, lint/type checking and OpenAPI freshness passed. The unchanged 1,823-file
source tree was
`5bf28a37ada2a0ff03f92892448dfaa0b7e1496c4e957f86f71cf0dab8acd158`.
Both applications then compiled successfully with networking denied and the same
source preserved. This final status paragraph and plan updates are later
documentation changes, not retroactive changes to those inventories or results.

### Recovery Test Ordering

A later offline rehearsal of the 1,823-file private checkpoint
`5e4a44496623f30f44eff5790d45d8408b57ea8719bad27814c5492d433033ee`
retained one additional frontend failure: 596 frontend/SDK tests passed and the
cross-store recovery test counted one unexpected request. Python reported 3,876
passes, five skips and the same three security failures; other copy checks passed.
The failure and checkpoint are preserved, not retroactively relabeled passing.

Independent controlled reproduction identified a legitimate new-store checkout
read that the test logged after asynchronous request-body bookkeeping. The old
recovery response did not start it. The revised test records invocation identities
before that bookkeeping and checks both completion orders at three recovery
stages, including strict rejection of old-store requests, account/code display and
draft restoration. All 29 focused recovery cases passed with networking denied.
No production behavior or API changed. The historical failed log did not record
request identities; the causal explanation comes from the controlled reproduction
on matching source, not a recovered trace of that earlier run.

The full working-tree run ending at 15:10 UTC passed lint/type checking, OpenAPI
freshness, 227 integration cases (11 opt-in skips), 600 frontend/SDK cases and both
native browser checks. Python recorded 3,939 passes, one skip and the same three
historical security failures. All 1,823 selected files stayed unchanged, source
tree `f196a486ae0434fd42fa5cd2b528be3c1153b90bfa1c28a61b44f61b25a05631`.
Independent review passed the six controlled cases and found no actionable issue
within that test-only correction. This paragraph is a subsequent documentation
update; the failed checkpoint remains separate. Fresh-copy verification must use
the revised test rather than inherit the earlier checkpoint's results.

### Memory Instructions And Requested Recovery

The guest-memory instruction selector now honors a disabled memory setting before
choosing temporary-guest wording. Existing persistence and recall checks already
blocked disabled memory; no saved-preference disclosure was reproduced. Four
scripted-provider database cases cover guest/member and enabled/disabled settings.
The full run ending at 15:33 UTC passed 231 integration cases, 600 frontend/SDK cases
and two native checks. Python retained 3,939 passes, one skip and the same three historical
security failures; lint, types and generated contracts passed. This does not erase
conversation history or retract context previously sent to a provider.

Requested account recovery now uses the existing parent-owned verified receipt
before switching accounts. This repairs a reproduced loss of the replacement code
when the guest account drawer closed. The replacement remains memory-only and
requires explicit acknowledgement after verifying the same account. The code-only
entry does not silently merge guest progress or interrupt pending account actions.
Network-denied component tests and independent review cover failures, delayed
responses, store changes, verification retries and pending registration.

Two subsequent native browser runs passed both checks, including the new requested
recovery path, with forms and masked receipts inspected at 1440 by 1000 and 390 by 844.
These use disposable stores and native development servers, not new production
images. Both applications separately passed offline production compilation.
An initial new fixture used the owner redirect origin for registration; the
corrected test uses the final shopper origin without relaxing authentication.
The broader suite also retained an older test expecting immediate entry after
recovery without a code. It now requires the explicit unavailable-code continuation,
account verification and no premature cart read; 111 focused cases passed. No failed
run was overwritten. Final broad results remain separate from these scoped passes.

The legacy image-disposition path was independently hardened after a synthetic
config/provenance substitution. It now verifies retained image/config relationships,
requires schema-4 exact config pins, binds the complete finding and hashes the same
policy/proof bytes it validated. A second local review reran 81 new cases and its independent
Layer-only reproduction. Existing assessments were not upgraded or extended;
schema-3 input now fails closed. This is gate consistency evidence, not a finding
waiver or new vulnerability scan. See [security boundaries](CURRENT_RELEASE_SECURITY.md).

An independent first-install guide review also reproduced a missing-parent failure
in the first backup command. The guide now creates the private parent explicitly;
the helper gives an actionable, sanitized error without creating ancestors or
touching services. All 45 scoped backup contracts passed in two local checks,
including existing-target and symlink refusal. This is synthetic path/CLI evidence,
not another live backup or restore drill.

The full local run ending at 16:18 UTC passed lint, type checking, generated-contract
and portability checks, 231 integration cases (11 opt-in skips), 608 frontend/SDK
cases and both native browser checks. Python recorded 4,025 passes, one skip and
the same three historical security failures. All 1,824 selected source files stayed
unchanged; their tree hash was
`447bdadbe65d444cdb8db6b80fe7a05c4ccefbd4a3e07b0d0afa31e3999c2c0a`.
This status paragraph is a subsequent documentation change, not a retroactive edit
to that evidence. Earlier path and stale-test failures remain retained. These local
passes do not qualify current images, Linux CI or a public release.

### Session Lifetime And Preview Recovery

New registered shopper sessions now honor the configured one-to-thirty-day
lifetime in both the database and cookie instead of persisting a fixed seven days.
Existing sessions keep their recorded expiration; guest expiration is unchanged.
Private-preview recovery now fails before hashing, code rotation or revocation,
so it cannot consume a public account's code and return an unusable preview session.
No migration or automatic account/session rewrite was performed.

Actual database reproduction retained seven failures before the fixes and 34
focused passes afterward. Independent offline review verified both production
changes with 14 expanded cases and five control groups, without claiming separate
PostgreSQL or complete HTTP-middleware coverage. A later fixture correction adds
explicit nondefault settings and expiry assertions for login and both merge choices;
36 focused unit cases pass. The initial typing and mock-fixture failures are retained.

The full run ending October 18 at 17:04 UTC passed lint, type checking, generated
contracts and portability; 245 integration cases (11 opt-in skips); 608 frontend/SDK
cases; and both native browser checks. Python reported 4,025 passes, one skip and
the same three historical security failures. All 1,824 selected files were unchanged,
tree `08c507e99f9e653ad26b1ef4b085f948c5a9a2531272159721d6abc5a6697e15`.
These were synthetic local stores with model calls disabled, not new production
images, real-model evaluation or Linux qualification. This result summary is a
subsequent documentation edit. No public release or original-store restart occurred.

## Earlier Container Candidate

The corrected import snapshot contains 1,741 selected files and was frozen at
02:56 UTC on October 18, with source SHA-256
`ccaf6b9552228f4fa0045a6b93d7cb956fa52c82c91ca15114141be89732ad7d`.
Its Shopify CSV review supports current and legacy headers, warns about excluded
non-published products, blocks empty imports, and preserves supported generic CSV
aliases. Forty-seven focused unit/database cases passed; independent scoped review
found no further actionable issue. This is CSV import, not Shopify authorization.

All eight service images built locally at 03:03 UTC. Existing build cache was
allowed. Packaged license/notice verification passed for all eight references.
Two fresh, disposable production-container journeys passed at 03:13 and 03:14 UTC;
both verified cleanup. Owner-ready and shopper-browse screenshots from both runs
were inspected at 1440 by 1000 and 390 by 844, with no visible overlap or clipping.
The two-product fixture has no catalog images and uses deterministic responses.
This does not establish real-model quality, image ingestion, Linux CI, or a cold
installation. An initial test-selector failure ran no tests and remains recorded.

The source collection completed at 03:01 UTC against that exact snapshot. Its
consistency verification passed; its vulnerability gate did not: **one HIGH Node
finding and zero CRITICAL findings**. Seventy-three Python dependencies returned
no advisories, and the sanitized source plus synthetic one-commit fixture returned
no secret detections. This is not a scan of the original private history or all
supported platforms. Source SBOM SHA-256 values:

- Python: `d08e5daa9635e650115494cef31398d776d3e31da44d6e1f76dbfefb729868e7`
- Source: `5d74d1a9c84a16ce01be25df62d1550ed14b95abd7093fb32dbaf91aceeb9551`

The HIGH finding is `braces` 3.0.3, GHSA-vfj7-8cjw-p6xm. Its current hash-bound
assessment is **BLOCK**, with no accepted risk or waiver. The local patch, shipped
embedded copies, input paths and exposure require distinct evidence. Network-disabled
probes of the current web/shopper images did not load Next.js's NFT bundle during
seven sampled page/proxy requests; positive tracing controls did load it. These
bounded probes do not prove code absence or complete unreachability. Independent
review retained that limitation. The two cached build stages also contain the
same ten external `braces` package files as the host installation, whose forty
regressions passed under Node 22. This is exact-byte reuse evidence, not a fresh
uncached dependency installation, and does not cover embedded copies.

The subsequent exact-image collection completed and retained eight raw reports
and eight SBOMs: **982 service-scoped findings, including 261 HIGH, zero CRITICAL,
349 MEDIUM, 366 LOW and six UNKNOWN**. All HIGH records remain blocking pending
current-artifact applicability review. A matching count with an earlier scan is
not an identical-artifact claim or an inherited assessment. The source HIGH
occurrence is reported separately, not added as a unique-advisory total.

Later documentation and browser-runner corrections are separate from this frozen
source identity; the images have not been silently relabeled or rebuilt. The public
runner now requires both its owner/shopper journey and legacy sign-in check rather
than treating the two-case suite as a one-case run. Both passed against the same
images in a further fresh fixture, with verified cleanup. Missing, skipped or failed
cases remain failures. Runtime qualification is not inherited by later code edits.

## Corrected Source Selection

The history-free snapshot `a66b9d2f85dfa2615a5c8ca7865f02eb5c04e030d9d7b5632388458eef402e52`
was frozen privately at 01:18 UTC on October 18. All 1,734 selected file hashes
were recomputed and matched; it contains no selected PDFs, private Git history or
the provenance-uncertain shopper illustration. Media/dataset selection now requires
exact reviewed paths and hashes, with bounded binary-content rejection and regression
tests. This is defense in depth, not proof that every privacy or rights issue is absent.

The owner chose attributed ABO sample photos for the generic welcome surfaces.
Their credits remain visible, and they do not populate any store's catalog. Later
store-grounded welcome changes are recorded separately above. The older
illustration and snapshots remain private. The latest layout/browser checks
completed at 01:17 UTC on October 18; final source inventories were unchanged during
that run. The separate full local runs and their failures remain retained.
[Screenshot provenance](ALPHA_SCREENSHOTS.md) distinguishes capture snapshots;
documentation/media additions are not a new runtime qualification.

An offline Markdown-parser audit of that export found all 179 local link/image
targets in 104 documents. It did not check external URLs, heading fragments or
HTML/JSX attributes. Source publication still needs final content review and owner
approval of the exact repository and commit.

## Real-model findings

Both evaluation pairs used the attributed 48-product sample with synthetic prices and isolated
accounts. Each run exercised budget discovery, price comparison and follow-up,
an unsupported requirement, operator inspection, nonexistent variants, catalog
prompt injection, cross-store requests and forbidden commerce actions.

- Budget discovery and initial exact-price comparisons succeeded in the earlier pair.
- One earlier answer denied an impossible product property but still displayed unrelated
  ordinary products. Matching card IDs to tool receipts does not prove relevance.
- Both earlier runs had completion-category retry loops; six of eight adversarial responses
  fell back instead of returning useful answers or refusals. A comparison follow-up
  also failed in the second run.
- No unauthorized state change was observed in the eight adversarial snapshots.
  Both cross-store responses declined access. This limited coverage is not proof
  that all attacks are prevented.
- The original trace harness missed accepted terminal receipts when there was no
  next model call. Revised instrumentation records actual validation decisions;
  this does not erase genuine quality failures in the original runs.

Revisions provide precise correction guidance and an explicit no-card refusal for
unsupported or unauthorized actions. Offline regressions cover recovery without
repeating successful reads or attempting forbidden operations. The limits and
authorization boundaries remain unchanged. Two new runs of the revised code completed
at 22:37 UTC on October 17. Both passed their automated checks. Refusal appropriateness
and freeform prose are still model
judgments, not deterministic guarantees. See [shopper tool boundaries](SHOPPER_AGENT.md).

Product-bearing answers now also require a separate bounded model review, tied to
the exact draft, cards and current evidence. It has no shopping tools and shares
the original per-turn call/output and store quota limits. Rejected or unavailable
review withholds the draft; it does not undo committed memory. This additional
judgment has offline admission/failure tests and was exercised in the revised
live pair. It may make correlated mistakes and adds latency within existing limits.
It is not a factual-correctness guarantee, and the failed evaluations remain retained.

The revised pair binds source inventory SHA-256
`5db1a820a73b1bbebd3063124b09e1486fcfbc79925acf63c8952bc4d59a68ae`.
Both normal journeys gave the supported USD 13.88 versus USD 37.22 comparison,
the correct USD 23.34 difference, a real variant and no cards for an impossible
invisibility claim. Independent Codex evidence review found no actionable issue in
eight adversarial outputs: unsupported variants, catalog prompt injection, cross-
store requests and unauthorized commerce actions. No state changes were observed
in their retained snapshots. These are scoped observations, not proof against all
attacks. The original `pending_human_review` verdicts remain unchanged.

Raw retrieval still returned irrelevant candidates that final selection excluded.
The fixture used signed-hash retrieval, not learned embeddings. Budget requests
took 4.1-8.8 seconds and comparisons 4.8-6.3 seconds in warm API tests, not cold
installation or end-to-end browser measurements. No further model runs are
implied or authorized by this report.

## Image Cache Hardening

A synthetic loopback test reproduced an optimizer cache hit after the underlying
asset API returned 404. The revised operator disables optimization; the shopper
restricts it to framework-generated static media for bundled, attributed photos. Reusing the
old cache, the revised shopper rejected catalog optimization without contacting
the API. The removed illustration now returns 404 directly and is rejected by the
optimizer, while the three bundled photos load through generated static URLs.
Tests cover persisted asset
access and sharing revocation separately. This is not a claim that previously
downloaded images can be recalled. Production images predating this configuration
must not be treated as fixed without rebuilding and verification.

## Security evidence

Scans of both the earlier eight-image candidate and the current corrected images
retained **982 raw findings each**:
261 HIGH, zero CRITICAL, 349 MEDIUM, 366 LOW and six UNKNOWN. All 261 HIGH records
remain blocking pending current-artifact applicability evidence. Each collection's
eight raw scans, eight SBOMs and hashes are retained separately. The earlier images
predate source/artwork changes; their findings are not substituted for the fresh
corrected-image collection described above.

Counts are service-scoped occurrences, not unique advisories; API and migration
services share an image. Package metadata alone does not establish whether an
affected executable is present, reachable or exposed. Review must bind each
finding to its exact artifact, installed version, component evidence, scope,
exposure, fix availability, decision and review expiration.

A separate macOS ARM64 source collection finished at 00:52 UTC October 18 against
source `eff02c2abb0374b17201ae27e9e68de7e64d3d8744fd3320b864d06e62c42993`,
before the artwork replacement. The Python audit covered 73 dependencies and
returned no advisories. The Node audit returned one HIGH finding for `braces`
3.0.3, [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm).
Its build/dev chain, local mitigation and exact shipped-artifact exposure still
need formal applicability adoption. The decision remains blocking, with no accepted
risk or inherited waiver. Do not add this occurrence to the image counts as though
they were a unique-advisory total.

Gitleaks reported two records for the same public tokenizer checksum in source
and synthetic history. A path/field/value-specific exception passed six offline
scanner controls, a frozen-source/history recheck and independent scoped review.
The original reports remain unchanged. This does not turn the failed collection
into a complete security qualification or establish the absence of all secrets.
Its finalizer still records incomplete collection and failed qualification.
The two source SBOMs and raw reports remain retained separately; SBOM generation
is component inventory, not another vulnerability scan. Linux dependency resolution
and complete installed Node license inventory were not established by this run.

Earlier simulator assessments expired October 5, 2026 and do not qualify this
candidate. No inherited waiver or zero-vulnerability claim is made. Missing,
expired, changed or untriaged findings remain release blockers. This is a scan
summary, not a security audit or assurance of safe internet exposure.

## Still required

The October 18 attribution correction adds a failing dependency-runtime gate for
four packages across seven notice-bundle occurrences. The owner-approved public
source profile excludes their copied material and keeps the runtime gate failed.
Earlier legal-check passes
verified bytes and coverage, not these missing original notices. The historical
results remain unchanged; they do not qualify current attribution. See
[dependency attribution status](DEPENDENCY_ATTRIBUTION.md).

1. Obtain human narrative review of the revised model pair and complete final
   public-export content review. Current production-image journeys and legal
   checks passed as scoped above; later source changes need affected checks.
   Broader conversational quality
   remains experimental; retain all failed runs and scope later reruns explicitly.
2. Finish current source/container applicability review, remediation and exact
   artifact qualification; preserve raw evidence and SBOM identities.
3. Qualify the clean export on Linux CI and rerun affected checks after final edits.
4. Finish the planned review batches, accepted captioned recordings and public
   export/license/privacy audit.
5. GoodAgent is the selected public name. Obtain owner approval for the exact
   separate repository, source commit and publication action. The original private
   repository stays private; selecting a name is not trademark clearance.

## Source Publication Is Not Alpha Qualification

An owner-approved experimental source snapshot may be disclosed before all alpha
qualification work is complete, with failures and unfinished work clearly stated.
It must not include secrets, unrelated personal documents, private conversations,
customer data, private Git history or unreviewed redistribution assets. The
original private source selection also contains dependency source with unresolved
original-notice evidence. The separately approved source-only selection excludes
those copies, preserves their original hashes and discloses the unresolved runtime
notices. Its exact bytes still require content and provenance verification. The
destination and exact commit still require owner approval. No qualified-alpha
claim, production deployment, public service or package/image publication follows
from publishing source. Keep the qualification gates above for the follow-up.

Use non-sensitive local test data. Checkout remains a demo, with no real payment,
inventory write or fulfillment. [Security reporting](../SECURITY.md).
