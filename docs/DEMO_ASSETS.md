# Historical Simulator Demo Assets

These assets document the older simulator, not the current owner/shopper alpha.
The recipe below is historical and needs adaptation for the explicit
`legacy_demo` runtime profile and the simulator's current `/lab` route. It is not
a working current-alpha recording command. Use [Alpha Demonstrations](ALPHA_DEMOS.md)
for the new store journey; do not run simulator captures against an existing store.

These six intended screenshots are generated from real local API/worker/Qdrant
state, not browser mocks or hardcoded favorable metrics. Do not upload them or
the optional video until the owner separately approves public publication.

## Reproduce

Use a bootstrapped checkout, Docker with Compose, and a **fresh dedicated project**.
The capture refuses to run if the project already has saved goals. It never resets
someone else's demo, changes global Docker context, or uses a personal browser profile.
Use new unused ports/project name for another capture, or deliberately remove only
your previous disposable capture volumes after retaining any evidence you need.

```bash
make bootstrap
make install-browser
export COMPOSE_PROJECT_NAME=opencommerce-capture
export WEB_PORT=53011 API_PORT=58011 POSTGRES_PORT=55451
export REDIS_PORT=56391 QDRANT_PORT=56352 QDRANT_GRPC_PORT=56353
docker compose up -d --build --wait --wait-timeout 180
CAPTURE_DEMO=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:53011 make demo-assets
```

The script uses a clean Playwright Chromium context, seed 42, UTC, en-US and
1440 x 1000 (1280 x 1000 for the search scene). It also checks 390px mobile overflow and stores full-page review
captures in ignored `apps/web/test-results/capture/`. No external screenshot
service, public artifact host, account session, token, or personal tab is used.

## Scenes

| File under `docs/assets/demo/` | Runtime evidence |
| --- | --- |
| `dashboard.png` | Goal, actual observations, constraints and seven virtual days |
| `goal-configuration.png` | A finite-parser draft, reviewed before activation |
| `agent-trace.png` | Persisted observation/planning/enforcement/execution trace |
| `rejected-policy-action.png` | Real denied 10% discount under a separate 5% policy fixture |
| `kpi-observations.png` | Actual KPI movement and matched synthetic baseline; no positive-delta assertion |
| `hybrid-search-trace.png` | Live Qdrant results, score components and hard filters |

The ordinary acquisition demo uses the default 15% discount maximum. The rejection
scene is explicitly separate, with a 9,000-customer stretch target and a tightened
5% maximum. The script restores the earlier policy in a finally block. It does
not weaken policy or fabricate an excessive default proposal to tell a story.
The primary goal is paused after observation; completed effects are not reversed.

`manifest.json` records captions, browser version, seed, observation and SHA-256
for every intended asset. No absolute machine path, account identifier or secret
is included. It records elapsed walkthrough time separately from stack startup.
UUIDs and wall-clock timestamps are naturally different on each run: behavior and
inputs are reproducible, image bytes are not a golden benchmark.

## Local Video

For an optional browser-only recording, add `CAPTURE_VIDEO=1` to the capture
command on another fresh project. Playwright writes local WebM files under the
ignored test-results directory; it does not publish or commit them. Review every
frame before any separately authorized use. The clip includes waits, not an edited
speed claim. An optional local GIF conversion with an already-installed ffmpeg:

```bash
ffmpeg -i capture.webm -vf 'fps=10,scale=960:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse' demo.gif
```

Only the six selected PNGs and their manifest belong in version control. Keep
failure traces, raw recordings and mobile inspection captures local/private.
