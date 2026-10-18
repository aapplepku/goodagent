# Inspectable decision trajectories

These examples come from the retained development three-arm evaluation, seed 71.
They are actual controller decisions, not action-injected workflow fixtures, and
not independent held-out cases. Cycle indices below are zero-based within the
twelve evaluation days after warmup. See the complete comparison for adverse
profit, attribution caveats and late pending measurements.

Each compressed raw file contains `decisions`, `actions`, `observations`, initial
world/observations and final state. Read
`decisions[i].summary.merchandising_decision.candidates` for every inspected row:
goal permission, observed opportunity, sample sufficiency, generation, compiler,
full policy evaluation, disposition and reason codes. Read `actions` separately
for exact approval, dispatch, receipts and outcomes. Selection is not execution.
The adjacent manifest hashes the raw files and the original source snapshot.

## Search considered, not assumed useful

File: `results/development-three-arm/crowded_boots-71-revised.json.gz`, cycle 0,
run `5358ff0d-716c-5202-9b33-a8c371ef5744`.

`search:merch_hiking_boots_8` is allowed and has sufficient observations, but no
supported exposure-gap opportunity. It is not submitted to compilation. The
crowded catalog and excess stock do not establish underexposure by themselves.
The price alternative is rejected by the combined effective-discount limit;
promotions are prohibited by this reviewed no-discount goal. `pdp:complements`
passes compilation and requires approval, then executes with inventory priority
0.05. Unchanged remains explicit but is not selected. This adverse-profit case
does not prove search-selection skill. Authored underexposure tests are separate
path coverage, not an autonomous effectiveness result.

## Price versus alternatives

File: `results/development-three-arm/bounded_offer-71-revised.json.gz`, cycle 2,
run `d0e03cd8-aa97-52c0-a5ec-1f12afd764b8`.

The selected `price:merch_headphones_3:14820` changes one variant from 15600 to
14820 USD minor units for 168 hours. Recorded availability is 78 units and peer
IDs are headphones 1, 2 and 4. Known per-unit contribution profit decreases from
7036 to 6278 minor units; projected margin is 0.4236167 versus a 0.25 floor.
Predicted orders and store profit remain null. This is an approved experiment,
not a forecast that lower unit profit will be offset by demand.

Three other price candidates and four 5% promotion candidates also compile and
require approval. They are deferred with
`ONE_INTERVENTION_PER_CYCLE_OTHER_CANDIDATE_PREFERRED`; fewer affected variants
and the declared stable tie-break prefer this candidate. The same product's 10%
promotion is rejected before compilation with
`LARGER_DISCOUNT_WITHOUT_RESPONSE_EVIDENCE`. Its search row has no supported
exposure gap. The existing offer's disable row lacks matched observations, and
the active PDP reassessment has no descriptive stop signal. Full per-rule policy
records are retained; no competing proposal is silently treated as an execution.

## Reassessment is not another markdown

Same file, cycle 4, run `1eb44096-d540-5221-85da-e3c0fb09d99c`.

`price-reassessment:merch_headphones_3:v1` waits for two complete days, 200
exposures and 20 orders per matched window. Another markdown and new promotion
on that product are rejected: current price is already below observed peer
median, prior monetary response is unidentified, and the active price must first
be reassessed. Other valid candidates are denied by the unchanged three-active-
intervention policy. Unchanged is selected. The existing offer's disable row also
waits for evidence; it is not called harmful just because conversion is low.

By cycle 11, run `481708ca-1bbc-5648-a450-0b106087c3de`, the first price has
expired/restored. Its history and insufficient-data assessment remain, and another
markdown or promotion is still refused without response identification. Past
orders, discounts and losses are not reversed by restoring the configuration.
These cases do not demonstrate a controller-selected observational stop. Separate
authored tests distinguish known-bound stops, observed deterioration and waits.

## PDP revision after version zero

File: `results/development-three-arm/compatible_panels-71-revised.json.gz`, cycle
9, run `d078b839-b036-5edb-935e-b271dae49ddc`.

After the first seven-day experiment expires and fresh current-version evidence
accumulates, `pdp:complements` compiles with expected version 2, not 0. It requires
exact approval and executes a new revision through the same serving path.
Compatibility, availability, relevance 0.55, brand diversity and exclusions
remain. Monetary families are prohibited by this search-only goal. The second
measurement is still pending at the evaluation horizon. The first experiment's
nonadverse descriptive reassessment is not proof of causal benefit.

The durable version-4-to-5 integration test uses authored observations and is
explicitly only selection/approval/concurrency/serving path coverage.

## Insufficient history

File: `results/development-three-arm/thin_history-71-revised.json.gz`, cycle 0,
run `20699a91-88ee-589b-9002-6b870c644c55`.

All 195 diagnostic rows retain their disposition. Search and PDP have neither
complete recorded days nor matched observations; no draft is compiled. Unchanged
is selected with `NO_ELIGIBLE_INTERVENTION`. All three arms have identical profit.

## Runtime inspection

The existing `GET /v1/runs?goal_id=<id>` and `GET /v1/runs/<id>` endpoints expose
the persisted candidate ledger in `summary.merchandising_decision`. The browser
timeline shows run status and trace events, not this complete summary. Its event
JSON alone is not the candidate ledger. No UI redesign or new endpoint is added.
