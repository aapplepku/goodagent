# Basic-Mode Catalog Demonstration

This is a separate, private **no-AI** demonstration of catalog setup. It does not
complete the [real-model recording pair](ALPHA_DEMOS.md), qualify a release or
authorize public sharing of source or video. A private take passed on October 18,
2026, 13:44-13:46 UTC, with separately reviewed captions. Earlier failed takes are
retained; no recording has been published.

## Scope

The owner explicitly chooses the bundled, attributed 48-product Amazon Berkeley
Objects sample, reviews it and confirms the current review. The actual worker
prepares packaged images, builds the local hash-based search projection and verifies
its product count. No external images or learned embedding models are downloaded.
Prices and stock are synthetic; [attribution and sample limits](../examples/datasets/amazon-berkeley-objects/README.md)
remain applicable.

A private shopper preview tests the literal name **Serene** in visibly labeled
Basic mode. The recorder requires the expected catalog product and USD 13.88
synthetic price, not merely a completed request or a ready index. After that test,
the owner acknowledges image review and demo-only checkout and explicitly enables
the exact catalog. A separate fresh guest opens the enabled local store and browses.

The owner page, preview tab and guest page are separate clips, each with its own
captions. Account setup happens off-screen with synthetic credentials; session
state stays in memory. Real waiting times and failed takes are retained. No payment,
account registration/recovery, memory demonstration or conversational model is part
of this story. A successful literal lookup is not general relevance validation.

## Runtime Boundary

Use only the opt-in Python test fixture, never the existing real-model recorder or
an already-configured store. It requires explicitly supplied local QA dependency
endpoints. It creates a random test database and unique worker queue, starts owned
API/worker/apps, and terminates only those processes afterward. Existing dependency
services are reused, not claimed to be newly isolated containers; search checks
are scoped to the disposable tenant, catalog and version.

The fixture fixes self-hosted/deterministic/hash settings with environment-file
loading disabled. It rejects model construction/dispatch and remote-image branches,
counts attempted violations, and constrains Python connections to the supplied QA
endpoints. Browser requests are restricted to the two owned app origins. These are
test-harness controls, not production security controls or a machine-wide firewall.
API and worker model guards remain active throughout the take.

Database connections in this fixture require the explicit QA username/password,
exact loopback endpoint and owned database. Its capture-only driver wrapper
disables TLS/passfile fallback and rejects credential-file access; the supervisor
alone may also connect to the QA administrative database to create/drop its test
database. This avoids consulting the user's PostgreSQL home credentials. It does
not change production database behavior or authorize plaintext remote databases.

Durable checks run before importing, after preview search and after stopping the
owned writers. They require zero model-usage and inference records, the exact
review/import/catalog identity, 48 prepared image assets, verified indexing and
explicit publication. Empty usage tables alone are not evidence of zero outbound
attempts; process and browser guard receipts must also pass. Failed image ingestion
or model fallback cannot qualify the capture.

## Private Evidence

Use a new output directory under ignored `.opencommerce` for every take. Do not
reuse a directory containing evidence. Output, runtime evidence and Playwright
scratch output must be distinct and nonsymlink. The fixture records private logs;
they are not uploaded by hosted CI or included in the public source export.

The output retains original page videos, separate English WebVTT captions, selected
screenshots, an HTML player and a bounded receipt. Inspect all clips and caption
alignment, every visible product/price, and all selected screenshots before deciding
whether they are usable. The caption clock is wall time measured around page
creation; automated assertions do not replace visual inspection. No shortened waits
or edited pixels are implied.

Final verification must retain the source inventories before/after, actual browser
and tool versions, stage-specific database facts, zero-violation guard receipts,
asset and media hashes, and any failed take. Do not publish authentication logs,
cookie/session exports, private transcripts, bootstrap tokens or recovery codes.
The installer and ordinary [first-store guide](FIRST_STORE_DEMO.md) remain the
user-facing entrypoints; this capture fixture is developer/release tooling.

## Recorded Result And Limits

The passing take verified 48 imported products, 48 decoded local images, the matching
48-product search projection, private Basic search, explicit local sharing and a
fresh guest's catalog lookup. Process/browser guards reported no violations, and
both model-usage journals remained empty. The disposable database was removed;
original stores were not changed. These are scoped fixture observations, not a
machine-wide egress or security qualification.

The three original clips last 67.08 seconds (owner), 14.16 seconds (private preview)
and 11.92 seconds (guest). No frames or waits were shortened. Raw wall-clock captions
are preserved; a separate derivative aligns ten captions to independently inspected
encoded scene times. Copied videos are byte-identical to the originals. Final
photographed product results remain visible for more than five seconds.

The private player passed duration, caption and overflow checks at 1440x1000 and
390x844. A follow-up derivative puts captions below the video after independent
review found that overlaid captions obscured narrow-screen product details. All ten
cues were checked at both player sizes, with native captions retained in fullscreen.
These are desktop recordings scaled within a player, not mobile application
journeys. Selected final-scene screenshots were visually checked; this does not
constitute inspection of every encoded frame or qualification of mobile usability.

Source inventory SHA-256 for the take:
`4b21adf87184e51bc892e75825a2d99a2553d179d21e16280631248f8b5eeb22`
(1,821 selected files). Private evidence retains video/caption hashes, raw failed
takes and independent review. The source inventory is not a published Git commit.
See [validation status](ALPHA_VALIDATION.md) for current app checks and the four
remaining security/attribution gate failures. Real-model recordings, release
qualification and publication approval remain incomplete.
