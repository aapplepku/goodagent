# Why v1 selected prices but not search or PDP

The read-only replay reproduces all nine seed-11 initial decisions exactly,
including draft IDs and parameters. The archived successful 27 action arms still
contain 99 cycles: 34 prices, two promotions, 36 two-day cooldown waits, 24
no-supported-opportunity waits and three zero-history waits. No counters or
expected results were changed. See `v1-diagnostic-ledgers.json.gz`; hypothetical
family-isolation compilations are labeled and were never executed.

## Selection and suppressed alternatives

- Search comes before money in the code; price ordering did not suppress an
  eligible search draft in these first-cycle replays. None satisfies the joint
  excess flag, existing order, category-peer 200 exposures, below-half-average
  exposure and no-active-boost predicate. Category peers also mix different
  product families and query populations. A zero-exposure product cannot get the
  required prior order, so the test excludes the strongest underexposure case.
- PDP comes before money too. In explicit-complements seed 11 all 48 pair rows
  have a complement with orders, but every complement has at least 20 exposures
  on some PDP. These include its own family's alternative panels, not exposure
  beside the compatible anchor. Twelve pair rows have an anchor reaching 100
  all-surface clicks (maximum 162), but none passes the global complement-count
  test. Thus the absence is not simply low traffic or an absent relationship.
  The version==0 gate independently prevents all later revisions, even with
  adequate new evidence. Compatibility iteration order can choose the first
  passing pair; no competing-policy evaluation exists.
- Price and promotion inspect sorted product IDs, then the cheapest available
  variant with inventory above five. The first product satisfying the mixed
  conversion predicate wins, not the best-supported objective opportunity.
  `merch_food_containers_3` is first in all six price-selecting seed-11 replays,
  including poor-boots, active-boot-promotion and already-good fixtures. There
  are four to eight eligible products per such replay. Reordering the input list
  does not change the sorted result, but identifier priority decides the target.
- For that product, the first eligible lower base price is returned before any
  promotion. The family-isolation ledger shows a hypothetical promotion in each
  unrestricted price-selecting first cycle, suppressed before compilation.
  Only two later cycles reached promotion after earlier price eligibility failed:
  already-good seed 11 (food containers 3) and seed 23 (headphones 4), both at
  price version 2 after expiry. The lower-price candidate was rejected for
  PRICE_COOLDOWN, while promotion could reintroduce a markdown on that product.
  Finite candidate bounds/cooldowns are real constraints, not a profit ranking.
- Active promotions suppress further monetary proposals on their products. V1
  can disable one only for a known unit-margin or effective-discount violation,
  not because sufficiently observed outcomes are poor. The existing bounded
  offer did not violate those bounds; there is no automatic causal harm finding.
- Any command within the preceding 48 hours causes a store-wide early return,
  including unrelated targets/families. Durable policy separately reserves
  intervention targets until the existing seven-day measurement end. Serving
  control expiry and completed measurement are different states.

## Incompatible conversion population

The v1 numerator is product orders from search, PDP alternatives and complements;
its denominator is search exposures only, over the cumulative store history.
The read-only ledger also computes search orders linked from search batches.
They differ for 46-48 products in every nonempty replay. PDP clicks similarly
combine surfaces, and the underexposure predicate compares category-wide rather
than query-compatible exposure. The revised planner must use complete recorded
day windows and the batch's own redeemed order references for the same surface,
scope and window. No need to alter the simulator or archived evidence.

## Correction direction, before tuning

Enumerate bounded alternatives before one policy-aware choice; retain unchanged
as an explicit comparison and record complete reasons. Diagnose relative search
exposure within observed family/query contexts. Measure PDP eligibility and
exposure for explicit anchor/complement pairs, not all PDP surfaces combined.
Require observed conversion and known economics for any bounded price/promotion
experiment; low conversion alone does not identify elasticity. Preserve unknown
profit, existing policy/approval windows, exact versions, caps and rollback.
No evidence establishes that these corrections will improve aggregate profit.
