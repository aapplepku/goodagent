# Experimental Source Status

GoodAgent is usable for local experimentation, not qualified for production.
Use non-sensitive test data and loopback-only access. Source availability is not
permission to charge real customers or a claim that security review is complete.

## What Was Exercised

Two fresh native owner-to-guest journeys verified catalog review/import, indexing,
private preview, explicit sharing, browsing/search, product selection and demo
cart/checkout, with desktop/mobile captures. They used Basic mode and disposable
test stores, not live merchants or a current real-model acceptance run.

The application selection was frozen before a documentation-only status update:
`43c98df9f68c2bfb387f1ea1ac42338016d61922e020f67f7b7009d8153a4542`.
Lint, typecheck and OpenAPI freshness passed. Python unit/contract results were
4,135 passed, three skipped and four failed qualification gates. Integration:
257 passed, 11 opt-in skips. Frontend/SDK: 624 passed. Failed gates are retained,
not converted to passes. Later documentation does not inherit exact-source
qualification from these results.

## Known Limitations

- Four attribution/security qualification gates remain failed. Historical
  assessments do not qualify changed artifacts; expired assessments stay expired.
- Authentic notices remain incomplete for four dependency packages. The reviewed
  source-only export omits their copied payloads; it does not clear runtime image
  redistribution. See [dependency attribution](DEPENDENCY_ATTRIBUTION.md).
- An Add response lost in transit can leave the outcome uncertain. A new Add can
  be a second intent. Do not blindly repeat it; inspect the cart. Complete reload-
  safe, original-intent retry recovery remains unfinished.
- Cart requests admitted before account-data deletion or guest expiry are now
  fenced before replay/mutation. This does not close the broader retry gap.
- Real-model answer quality, clean installation/recovery, hosted checks and the
  planned model-backed recordings still need current-candidate acceptance.
- The checkout summary has a cosmetic singular/plural label issue. Demo payments
  never charge a card; no real payments, fulfillment or inventory writes exist.

## Latest Local Collection

The eight default local images built successfully. Cache was allowed; this was
not clean Linux CI, a cold installation or a deployment. Collection ended
October 19, 2026 at 03:00:35 UTC (October 18 at 11:00:35 PM Eastern).

Raw image scans contain **982 service-level finding occurrences**: 261 HIGH,
349 MEDIUM, 366 LOW and six UNKNOWN; none were labeled CRITICAL by that collection.
These are not counts of distinct CVEs. The source audit separately reports one
HIGH advisory for `braces@3.0.3`. Python audit and secret scanners returned no
findings within their tested scope; this is not a claim of zero vulnerabilities.

The raw collectors finished, but the combined evidence finalization failed.
A separate read-only source consistency check passed. Preserve both facts; a
completed scanner report is not a qualified evidence bundle or applicability
approval. The 261 image records and one source record remain pending current
applicability review. No fresh acceptance/waiver is implied by this summary.

Historical raw reports, assessments and SBOMs remain indexed in
[security verification](SECURITY_VERIFICATION.md).
The fresh private acquisition bundle is not uploaded automatically: generated
logs and image metadata require their own content/privacy review before sharing.
See [qualification requirements](PUBLIC_RELEASE_CHECKLIST.md) for the remaining
release conditions. Source disclosure and a qualified v0 release are separate.
