# Alpha Demonstrations

Capture two **private** browser recordings of a fresh, disposable self-hosted store:
catalog to working store, then shopper search/comparison/memory/demo checkout.
This is release preparation, not permission to upload media or publish the project.
Final media must be rerun on the frozen release candidate after branding is settled.

Current rehearsal status (October 17, 2026): both retained attempts stopped at the
first private-preview search because the model returned only an acknowledgement,
with no product results. A separately verified response-phase fix did not resolve
that observed failure. No complete demo pair has passed; do not use the partial
recordings as successful journey evidence.
Read-only inspection of the second attempt's retained test database found one
shopper model admission and only understand/respond activity, with no search or
lookup step. The provider's original response phase was not retained. Future
capture transcripts retain the public operational steps as well as the answer.

Subsequent fixes passed two bounded API evaluations; those are not new recordings
and do not retroactively complete these failed captures. The current
[desktop/mobile screenshots](ALPHA_SCREENSHOTS.md) come from a separate passing
deterministic browser journey, explicitly labeled with AI disconnected. A fresh
real-model capture requires its own bounded authorization and frozen candidate.

A separate [Basic-mode catalog demonstration](BASIC_CATALOG_DEMO.md) passed a
private take on October 18 without a model or remote image download. It records
actual 48-product sample import, indexing, private literal search, explicit local
sharing and fresh guest browsing. Its three page-specific clips and separately
aligned captions received bounded independent review. A subsequent private player
places captions below the video to address the review's narrow-screen occlusion
finding; parent browser checks cover all ten cues at both player sizes. The clips
remain desktop recordings, not evidence of mobile application usability.
This is not the model-backed pair above or publication approval.

## Prerequisites

- A separate, healthy self-hosted instance with no owner or existing catalog. Do
  not point the capture at your store. It refuses an already-configured instance.
- Real OpenAI conversation configured server-side and existing usage limits active.
  No key is supplied to the browser. A connection check must actually succeed.
- Installed developer dependencies and Playwright Chromium (`make bootstrap` and
  `make install-browser`). The Docker-first application setup alone does not install
  host browser-capture tools.
- The fresh instance's one-time setup token, supplied privately through the
  `OPEN_COMMERCE_E2E_SETUP_TOKEN` environment variable. Never place it in source,
  screenshots or reports. Synthetic accounts are created before recording starts.

Use the exact owner and shopper origins printed for that disposable instance,
without a `/manager` path. The ordinary setup uses `localhost`:

```sh
CAPTURE_ALPHA=1 \
PLAYWRIGHT_BASE_URL=http://localhost:OWNER_PORT \
SHOPPER_PLAYWRIGHT_BASE_URL=http://localhost:SHOPPER_PORT \
ALPHA_RECORDING_DIR="$PWD/.opencommerce/alpha-demo-attempt-1" \
npm exec --yes pnpm@10.17.1 -- --filter @open-commerce/web exec playwright test --config alpha-recordings.config.ts
```

Replace the two port placeholders with actual ports. The shopper origin must match
`OPEN_COMMERCE_SHOPPER_PUBLIC_URL`, including the hostname: `localhost` and
`127.0.0.1` are different origins to the recorder. Do not broaden its allowlist.
The output parent must exist,
the final directory must not exist, and symlink parents are refused. Use a new
directory and fresh instance for an approved subsequent attempt. Do not enable
Playwright traces/HAR/session exports: those can contain authentication material.

The capture has no automatic retries. It makes one short AI connection check and
four shopper turns: one private-preview search, then budget search, comparison and
preference saving. Keep the instance's existing shared budgets and configure at
most six model iterations, six tool calls and 1500 output tokens per turn. Provider
charges apply. A failed model answer is retained, never replaced with a canned one
or silently retried to produce a favorable recording.

## What Is Recorded

The owner explicitly selects the bundled CC BY 4.0 Amazon Berkeley Objects sample,
reviews and confirms it, waits for indexing, checks AI, tests a private preview and
explicitly enables sharing. The preview opens in another tab: its raw recording is
retained separately and the main clip's captions explain this, rather than implying
that a search was performed on the visible owner screen.

The shopper is already a registered synthetic account. The second clip shows real
model-backed search, the fixed product comparison, a committed preference save and
reload, product/variant inspection and explicit demo checkout. Guest onboarding is
covered by the separate self-service smoke test, not claimed as shown in this clip.

Passwords, bootstrap tokens, recovery codes and account-creation screens are not
recorded. Public sample descriptions and fixed synthetic prompts are sent to the
model. Prices, stock and engagement are synthetic, not current Amazon offers.
Checkout takes no money and does not write to any real store. See
[sample attribution](../examples/datasets/amazon-berkeley-objects/README.md).

## Inspect Before Use

The output contains two WebM files, English WebVTT captions, a local `index.html`
player, screenshots, a bounded synthetic conversation transcript and a manifest.
Original raw videos and failed attempts remain private. There are no cuts or sped-up
waits. Caption timing is based on the recorded page's creation; inspect alignment,
image loading, every answer, prices/variants and all visible text before approval.
An automated pass is not a narrative, privacy, accessibility or release approval.

Serve **only the recording directory**, never the repository or a parent containing
environment files. Use an unused loopback port; for example:

```sh
python3 -m http.server 8098 --bind 127.0.0.1 \
  --directory .opencommerce/alpha-demo-attempt-1
```

Open `http://127.0.0.1:8098/` and check both clips with captions enabled. Sidecar
captions require a player that supports WebVTT; the raw video alone has no burned-in
captions. Stop the local server when finished. Retain source/image identities and
actual model settings alongside the private capture, without credentials. A later
edit or shortened wait must be disclosed and retain its raw source/provenance.
