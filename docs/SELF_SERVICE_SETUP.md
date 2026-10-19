# Self-Service Stores

Private-development implementation. No hosted deployment, public publication, real
payments, inventory writes, or Shopify authorization/refresh is included.

Cancelling an import requires confirmation naming the file; dismissal leaves the
review and published catalog unchanged. Acknowledging the one-time owner recovery
code clears it from parent UI state, so switching between setup and the workspace
does not show it again. It is never saved in browser storage by this control.
An import awaiting review collapses the store profile and upload choices so its
mapping is reached sooner, especially on mobile. Expand "Store details and catalog
source" to edit those fields or choose a different upload; their values are retained.
Valid imports show a bounded product/variant table first. Expand **Edit field mapping
and currency** to change assignments; validation errors expand it automatically and
block confirmation. Optional warnings do not pretend required fields are missing.

## Runtime Profiles

- `self_hosted` is the new-install default. A console-issued, single-use token
  creates the first owner and a new store. Local identity extends users and owner
  memberships; usernames are not used to claim historical tenant data.
- `hosted` uses Authlib OIDC with verified issuer + subject identity, PKCE, nonce,
  single-use callback state, and server-side encrypted login grants. Provider
  credentials are deployment configuration, not an onboarding question.
- `legacy_demo` explicitly retains the existing configured demo tenant, accounts,
  catalog, simulator and tools. Its implicit manager role is not authentication.
  Do not expose it to the internet. Migration does not attach this tenant to the
  first new local owner or remote signup.

## Fresh Self-Hosted Setup

These commands are for a fresh installation. Do not replace the ignored `.env`
in an already-configured demo: it contains its database/model settings and may hold
the instance owner's secret key. Keep existing data in the explicit legacy profile
until a separate new-store setup has been chosen deliberately.

From the repository root, with Docker Engine running, Compose v2 or later, Python
3.12+ and `make` installed:

```sh
make setup
```

No host Node, pnpm, uv or Python package installation is required. Docker builds
the applications. Setup creates a mode-600 ignored `.env` only when it is absent,
with a random encryption key, database password, unique Compose project, and
available loopback ports. Re-running it preserves these values and existing data.
It never deletes volumes or issues an owner token automatically. Back up `.env`
separately from the database; losing the encryption key makes encrypted data
unreadable. Cold builds may take several minutes and need internet access.

New configuration is written and synced in a private temporary directory before
being published as `.env`. Disk errors or interruption before publication leave no
partial final file; free space or correct the directory permissions and retry.
Publication uses a same-filesystem hard link and never replaces a concurrent
installation's file. Filesystems without hard-link support fail safely; use a local
filesystem that supports it. An abrupt process kill may leave an ignored, private
`.env.setup-*` directory, but setup never treats it as installed configuration.
Existing environment files, including incomplete files from older setup versions,
are not repaired automatically. Preserve them and their associated data before
diagnosing a failed existing installation.

Setup prints the actual owner/shopper URLs and the exact console command for a
one-time owner token. With the default environment file and Compose plugin:

```sh
docker compose exec api python -m open_commerce.stores.console bootstrap
```

Open the printed owner URL (normally `http://localhost:3000/manager`). Enter the console token (valid for 30 minutes),
store name, username and password. Store the one-time recovery code privately.
The token cannot be replayed and existing private data is not assigned to this owner.

Existing files are never repaired or overwritten automatically. For a manually
configured `.env`, restrict permissions with `chmod 600 .env`, check that the profile
is `self_hosted`, and supply a random base64-encoded 32-byte encryption key. Do not
change the database password on an initialized Postgres volume without a separate
database credential rotation. The default Compose password is retained only for
compatibility with older installations; new generated environments use random values.
The setup helper refuses `legacy_demo` and `hosted` profiles. Keep your existing demo
in its original checkout and use another checkout for a fresh installation.

To prepare configuration without starting services, run
`python3 scripts/setup_self_hosted.py --configure-only`. An isolated check can use
`--env-file .opencommerce/test-install.env` after creating the parent directory.
Start or rerun that installation with
`python3 scripts/setup_self_hosted.py --env-file .opencommerce/test-install.env`;
`make setup` always selects the root `.env`.
Use the printed command, including that file, for every subsequent Compose action.
Setup ignores ambient application/Compose overrides so a shell's old demo settings
cannot silently replace the selected file. `DOCKER_CONTEXT` is retained for an
explicitly selected local engine. A port selected at setup can still become occupied
before startup; report/check the conflict and retain volumes rather than resetting data.

For optional real conversation, set `OPEN_COMMERCE_MANAGER_MODEL_PROVIDER=openai`
and `OPEN_COMMERCE_OPENAI_API_KEY` privately in the installation's environment file,
then rerun its setup command.
A blank or whitespace-only key is treated as missing, not as a configured model
credential. A nonempty key still needs a successful connection check.
Both agents use the server key. Model calls incur provider costs and remain bounded
by configured request/token limits. Never put keys in screenshots, chat, or Git.
Without a key, browsing, product details and demo cart work; deterministic replies
are not a real conversational model. New non-model replies explicitly say
**Basic mode: AI chat is not connected.** The label is saved with the reply, so
reloading history preserves its original mode even if a model is configured later.
Existing historical replies are not rewritten. Verify connection separately in store setup.

For native development, use the configured PostgreSQL/Redis/Qdrant endpoints,
`make dev-local`, and issue the bootstrap token using the same root environment:

```sh
.venv/bin/alembic upgrade head
.venv/bin/python -m open_commerce.stores.console bootstrap
```

`make dev-local` prints the actual ports. No shopper provides an AI key. The
self-hosted instance owner configures the server key; hosted mode uses the service
credential. With no model connected, catalog browsing and demo cart remain usable.

### Self-Hosted HTTPS

For a self-hosted TLS ingress, configure the exact external HTTPS origins in
`OPEN_COMMERCE_PUBLIC_ORIGINS` on the API, worker, and both clients, and configure
the allowed API hosts in `OPEN_COMMERCE_PUBLIC_HOSTS`. Keep the API and dependency
ports private. One configured HTTPS public origin makes merchant, shopper, and
private-preview cookies `Secure`, including when the internal Next.js-to-API hop
uses HTTP. Untrusted `Origin` or `X-Forwarded-Proto` headers cannot change this
cookie policy. Do not mix public HTTP login with this HTTPS configuration: browsers
will not send Secure cookies over ordinary HTTP. Local loopback-only development
with no HTTPS public origins continues to work over HTTP.

This cookie protection is not a complete TLS-ingress or deployment qualification.
Validate the actual proxy and HTTPS behavior before exposing an installation.

## Products, Preview, Share

1. Upload a generic or Shopify CSV, explicitly choose sample products, or explore
   without data. Only the first two options create catalog content.
   **Use sample products** now stages 48 attributed Amazon Berkeley Objects
   listings with images, through the same explicit review and confirmation flow.
   Sample prices, stock and engagement are synthetic, not current offers.
2. Review automatic field mapping, currency, product/variant rows, and line-numbered
   errors. Correct mapping or upload corrected rows. Confirmation is blocked while
   product errors remain. The new upload endpoint accepts UTF-8 CSV up to 20 MiB,
   10,000 rows and 64 columns. Legacy chat profiling retains its smaller limit.
3. Confirm products. Durable workers ingest supported raster images, build the
   search projection and verify counts. Progress is persisted, failed indexing can
   be retried, and the currently shared version stays available.
4. Choose **Open shopper preview**. Verified previews open directly in chat;
   send a product-name search. **Browse catalog** is still available, and shared
   public store links continue to open browsing first. Opening chat sends nothing
   automatically and makes no model request.
   Browsing alone does not complete **Shopper search tested**. Basic mode can
   complete this check; **AI connection verified** is optional for sharing.
   Preview grants are short-lived, one-use links; their sessions are scoped to this
   exact store/catalog and cannot call merchant APIs. AI connection verification
   is a separate synthetic probe.
5. Review image issues, acknowledge demo-only checkout, and enable the store link.
   Publication records the exact reviewed catalog, an idempotency receipt and prior
   version. Disabling sharing immediately denies ordinary guest/store access.

An unavailable storefront shows a retry action without exposing cached products.
The same gate applies when an already-open shopper receives the store-wide
`STORE_UNAVAILABLE` denial: the catalog and its polling are removed from view.
This is checked on requests, not instant server push; an idle page can retain
previously loaded data until its next check. Ordinary transient failures retain
useful last-loaded data and are not treated as publication revocation.
After the owner restores sharing, shoppers can choose **Try again** to reopen the
store; this does not clear their session or cart. Retry is explicit, not an automatic
request loop. Expired private-preview links still require a new preview from setup.
Opening a fresh preview link in the same store tab also exchanges it once and
removes its fragment. Failed grants are not replayed automatically. Store requests
remain bound to the store that started them; navigating to a different store does
not retarget an earlier request. Abandoned initialization does not start another
guest-session request, but an already-dispatched operation may still complete.
Closing the store or replacing its preview removes unsent in-memory text along
with the old view. Persisted conversations, cart and scoped recovery receipts are
not deleted. Update the API and shopper client together for the dedicated denial
code and recovery behavior; older clients do not gain this UI protection.

CSV setup currently supports USD, EUR, GBP, CAD and AUD, all using two-decimal
minor units. Other currencies are rejected; zero- and three-decimal currency
support is not implemented. A preview link alone does not pass the search check:
the shopper agent records the exact preview catalog after a successful search.
Image-issue acknowledgement belongs to the explicit sharing confirmation.

Setup is resumable from persisted imports and readiness. Encrypted raw uploads
expire after 24 hours and are erased immediately on confirmation/cancellation.
Reopening setup resumes Products for an unconfirmed upload, Preview for confirmed
products, and Ready to share for an enabled store. Optional activity-report failures
do not block import review. Sharing remains disabled until the exact catalog has
been tested in shopper preview; readiness refreshes when returning to setup.
During indexing, setup keeps refreshing until both import and store-readiness
snapshots settle. A completed import must not leave the preview button stuck on
an older running snapshot; no manual refresh is required for that transition.
The catalog route also requires owner sign-in. Its **Indexed** badge describes the
search projection, not permission for guests to access the store.
Workspace Home's **Connect data**, the Data drawer's **Upload or review catalog**,
and catalog attachments return to this same Products review. A successful upload
does not start indexing: choose **Confirm products** after reviewing it. Changed
field assignments or currency must be validated again before confirmation.
Confirmation is bound to the exact uploaded file, field mapping, and currency
shown in that review. If another tab changes it, **Review latest mapping** reloads
the current preview without confirming it; inspect it and explicitly choose
**Confirm products** again. Until then, indexing does not start and the encrypted
upload remains available within its retention period. An uncertain confirmation
retry keeps the same reviewed intent and request key rather than applying later
edits. Older clients must refresh after upgrading the API; confirmation without
the reviewed-state fingerprint is rejected. Previously confirmed imports remain
readable, but a legacy report without a fingerprint cannot authorize another
confirmation. This does not change the currently shared catalog.
While an import is queued or indexing, Home, Data and Preview show its job status
and verified-product count. Queued work has an indeterminate bar, not an estimated
percentage or time remaining. The generic limited-mode banner is replaced during
indexing and disappears once the index is verified. Existing usable catalogs stay
available while replacements are built; verification does not enable public sharing.
Optional engagement uploads remain in the workspace. Legacy direct Shopify
connection controls are not offered in self-service setup; Shopify CSV exports
use the same reviewed upload flow.
Cancellation closes unconfirmed staging; after confirmation, keep the old published
version or upload a replacement. Raw product rows are not sent to the model.

Setup follows one selected import at a time. Its review, catalog, index status and
preview checklist refer to that same import, even when uploading identical content
reuses an older catalog version. A new, unconfirmed upload does not inherit the
previous catalog's verification. Cancelling or expiring unconfirmed staging resumes
the previous eligible import, including a failed import that can be retried.
Confirmed imports remain resumable after their raw-upload retention period ends.
None of these setup selections changes the publicly shared catalog; publication
still requires explicit confirmation of the reviewed, verified version.

Image ingestion accepts public HTTPS only, pins validated public DNS addresses,
rejects redirects/private destinations, caps downloaded bytes and decoded pixels,
and interrupts HTTP transfers after 20 seconds even when data trickles in,
and re-encodes supported images to PNG. Decoder selection is restricted to JPEG,
PNG, WEBP and GIF before opening an image, rather than decoding an unsupported
format and rejecting it afterward. This does not sandbox the image libraries or
eliminate their security-review requirements. Assets are stored in the persistent
`catalog-assets` volume; the API reads it read-only. Owner access and shopper
publication/preview access are checked on each asset request. Unsupported/failed
images do not invalidate otherwise valid products.
The preview checklist lists affected product IDs and titles (the first 100),
with an explicit truncation indicator and a correction action.

The explicit sample additionally accepts fixed `sample-abo:` package identifiers.
Only manifest-listed public sample images are read, with SHA-256 verification and
the same raster re-encoding and tenant asset access checks. They are not filesystem
paths, and cannot be used to read arbitrary files or bypass HTTPS URL protections.
Sample source URLs, license and modification notice ship with the backend package.
The legacy ABO CSV's `/abo-images/` paths remain a legacy-client format; use the
sample action for offline self-service onboarding rather than uploading that file.

The store-specific shopper welcome shows catalog starter thumbnails only when
available. It does not fill image-free stores with unrelated sample photos. A
failed thumbnail leaves its starter action usable; already-downloaded images
cannot be recalled when sharing changes. Catalog assets remain authorized on
each request and are excluded from the public image-optimizer cache.

## Owner Session Changes

The workspace and catalog toolbar show the verified store name and public-link
slug. Settings, workspace reset and agent-history cleanup identify that same store
before an action is confirmed. Unsaved store-name edits do not change this label;
a successful profile save updates it only within the original active session.
This display is not a store switcher or an authorization grant.

The owner workspace, catalog and setup controls stay bound to the owner and store
whose data they display. Signing in elsewhere does not retarget an already-open
tab's profile edits, uploads, sharing, reset or sign-out to the new store. A
rejected operation closes the old view and offers **Check session** or sign-in.
Recovery discovers the active account explicitly; it does not replay your old
operation. Review the new store before starting another action. Requests already
accepted for the original store can still finish for that original store.

## Shopping and Privacy

Shared links use the shopper app's `/s/{store-slug}` route. Guests browse and chat
without a registration wall. Store-slug-scoped cookie names hold opaque session
tokens, preventing store switching from overwriting another visit. Slugs identify
stores; they are not secrets or authorization grants. Publication/preview checks
and tenant-scoped session validation control access. Guest context, preferences and carts last up to
24 hours; scheduled cleanup removes conversations and personal activity. Guest
memory is labeled temporary, never a permanent account save.
Background expiry rechecks that the account is still an active, expired guest
under the write lock before retiring it. Registration that was admitted before
expiry and successfully committed is preserved; repeated cleanup selections do
not retire the same account again. Starting registration after expiry still fails.

Deleting shopping data also removes personal monitoring rules, their evaluations
and configuration receipts. Already-started chat or monitoring work cannot
recreate that deleted personal activity afterward. New authenticated activity is
still available for an active account. This does not recall information already
sent to an AI provider or remove demo-checkout audit records; guest usage limits
and content-free memory opt-out receipts are retained.

Each guest receives at most ten admitted AI turns per visit/24 hours. Store-wide
daily request/token reservations are shared by API and workers. Hosted mode also
requires deployment ceilings. Reservations conservatively charge input bytes and
maximum output tokens, including uncertain failed requests; these are not claimed
as exact billed tokens. Exhaustion keeps history and browsing available.

Use **Save your progress** to register without losing the guest account's cart and
conversation. Existing-account sign-in preserves guest conversation history;
conflicting carts require an explicit choice and never silently combine quantities.
Old checkout previews expire and stock is revalidated by cart/checkout operations.
A cart retained from a different guest account receives a new version, requiring
fresh checkout review. Old guest checkout audit records are not transferred.

Account memory defaults on with disclosure. Turning it off disables both saving and
recall without deleting existing memories. Delete-shopping-data removes conversations,
preferences, personal operational logs and personal monitors. Identity and demo
checkout audit records are retained. Recovery codes are single-use and rotated;
session controls revoke active sessions.

For an existing shopper account, a guest can choose **Save your progress ->
Recover** and use its saved one-time code. Keep the returned replacement code
privately before continuing. The app verifies that account before showing the
code and again when continuing; a failed verification retries only the read, not
password recovery. This route does not import the guest's progress. For normal
sign-in with guest transfer, return to the current visit and use its sign-in tab.
Recovery codes are not saved in browser storage, so reload/navigation loses an
unacknowledged replacement. Requested recovery waits for other pending account,
memory, chat and cart actions, and does not report the current visit as expired.

For a local owner account, choose **Use a recovery code** on the sign-in screen.
Enter your username, saved recovery code and a new password, then keep the new
single-use recovery code privately. If the saved code is lost, instance console
access is required: reuse the Docker command printed by setup, replacing its final
`bootstrap` with `recover --username OWNER` (use your actual username). This issues
a replacement recovery code, invalidates the previous code and revokes that owner's
sessions; it does not change the password. Enter the replacement code in the browser
recovery form to complete the reset. Never share either recovery code in a report.

Completing local owner or shopper password recovery revokes existing sessions and
rejects sign-in attempts verified against the previous credentials but not yet
admitted. A shopper cart-choice prompt opened before recovery requires fresh
sign-in; it cannot transfer a cart using the old permission. The same applies to
an older deployment's pending cart-choice prompt after updating this protection.
Your saved conversations, preferences and carts are not deleted by recovery.
Console owner recovery also rejects sign-in attempts begun before its code rotation,
but a fresh login can still use the unchanged password until you finish resetting
it in the browser. Ordinary sign-out/session revocation is not a password reset.

Shopper history, memory, starter suggestions and cart load independently. Failed
sections have a retry action; unavailable cart/memory data is not described as empty.
A session-service outage offers connection recovery rather than a registration form.
Sign-out clears local account state only after the server confirms session revocation;
a failed request keeps the session visibly signed in and offers retry. Mobile drawers
leave these recovery notices accessible.

If a protected request reports an expired shopper session, the app hides cached
shopping data and offers sign-in or **Check session** without requiring a reload.
Unsent text and a failed chat request return only for the same verified account and
store. They remain in memory, not browser storage; reloading loses unsent text.
Starting a new guest visit is explicit and does not transfer the expired visit's
progress. A failed chat response cannot overwrite a newer draft. Retry reuses the
original request; dismissing it does not cancel work already received by the server.
Checkout and memory-change receipts remain scoped and require explicit retry.

The updated shopper client also checks that each protected request still belongs
to the displayed account. Signing into another account in a second tab cannot
retarget an old tab's cart action, memory setting, or deletion confirmation. The
old tab enters session recovery instead. **Check session** explicitly accepts the
new authenticated identity, without replaying the previous account's action.
Update the API and shopper client together; older clients lack this added check.

Product details expose variant choices, source prices and availability. Multi-variant
items require explicit selection. Browsing supports category, name/price sorting and
stock filtering. No model can bypass explicit cart and demo-checkout controls.
Shopper pending text reports waiting time, not invented search phases. Completed
tool activity appears with the reply. **Catalog available** describes availability,
not model connectivity or search relevance.

## Readiness and Monitoring

The setup checklist reads persisted catalog verification, image review, preview
search, AI connection check, demo acknowledgement and sharing state. Configured AI
is not equivalent to connected AI; a trained candidate is not an approved model.

Activity reports show successful searches, product selections, cart additions and
demo checkouts for the last 24 hours. Owner previews and explicitly marked sample
catalogs are excluded by default. These counts are not revenue, causal attribution
or proof of ranking quality. The search-to-selection cohort counts distinct shoppers
with a successful search in the last 24 hours and a later product selection in the
same store. It does not attribute that selection to a particular query or ranking model.
The API also exposes time to first preview and reserved
AI usage. Browser qualification records actual time to first useful product and
first preview separately from cold installation and provider latency.

Optional failed-import, failed-AI-check and empty-result presets run every five
minutes in the worker and display notices in-app only. AI monitoring reports the
last explicit connection check, not a continuous external-model ping. Empty-result
checks require at least five recent successful searches and report the bounded
observed window. Existing chat-configured operational monitors remain available.

## Hosted Gates

When using the low-level Compose command with a custom `POSTGRES_PASSWORD` that
contains URL-reserved characters, also set `POSTGRES_PASSWORD_URLENCODED` to its
percent-encoded value. `make setup` derives this safely in memory for startup and
does not change the password or print either value. Changing configuration alone
does not rotate credentials inside an existing PostgreSQL volume.

The explicit [hosted configuration reference](../infra/docker/hosted.env.example)
contains required variable names and deliberately unusable example addresses.
Keep actual credentials in deployment secrets or the ignored `.env`, not that file.

Set `OPEN_COMMERCE_RUNTIME_PROFILE=hosted` together with issuer, client ID/secret,
callback URL, encryption key, exact HTTPS public origins/hosts, deployment request
and token ceilings. OIDC callback must be on the configured public origin. API and
both UI deployments must share the configured public-origin allowlist. Terminate
HTTPS at a trusted deployment ingress; keep database/cache/vector services private.
Local process recovery and simulator job execution are disabled outside legacy demo.

Hosted sign-in intentionally supports self-service signup: a newly verified
issuer/subject receives a new, private store and owner membership, never access
to an existing store. Sharing starts disabled. Invitations and an application
signup allowlist are not implemented. For an invitation-only private pilot,
restrict eligible identities at the configured identity provider before enabling
sign-in; do not assume every identity in a broad issuer is pre-approved.

Authlib verification is tested against a controlled signed OIDC discovery/JWKS/token
fixture. The eventual hosted provider, internet ingress, backup restore, load limits,
and exact rebuilt image security/SBOM qualification require separate verification.
This work does not deploy a hosted service or refresh historical release evidence.
The existing source-hash qualification mismatch remains a failing release gate.

Identity integration follows the [Authlib Starlette OIDC adapter](https://docs.authlib.org/en/v1.7.0/oauth2/client/web/starlette.html).
Image destination and redirect checks follow [OWASP SSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html).

## Validation

Migrations `0020` through `0024` are additive. Back up before upgrading existing
databases. Do not downgrade/delete the owner database as a rollback mechanism.
The [cold-backup and recovery runbook](BACKUP_RESTORE.md) covers all four persistent
volumes, encryption configuration and exact images, with a new-project-only restore.

```sh
make lint
make typecheck
make test
make test-integration
make openapi
make check-openapi
OPEN_COMMERCE_RUN_INTEGRATION=1 OPEN_COMMERCE_SELF_SERVICE_BROWSER=1 \
  OPEN_COMMERCE_E2E_OUTPUT="$PWD/.opencommerce/first-store-run-1/browser" \
  .venv/bin/pytest tests/integration/test_self_service_browser.py -q -s
```

Integration/browser tests use disposable databases on the configured local dependency
services. Browser tests start their own API, worker and clients; no demo reset is
performed. Screenshots and measured-timing attachments are under the explicit
`OPEN_COMMERCE_E2E_OUTPUT` directory. Choose a fresh path for each run: Playwright
may clear an existing output directory. With no override they are under pytest's
temporary `tmp_path/browser`, not `apps/web/test-results`. Browser stdout and
service logs remain in pytest's temporary directory; keep raw authentication-bearing
diagnostics private. See [two-run reproduction](FIRST_STORE_DEMO.md#reproduce).

Before reusing an existing local demo, keep `legacy_demo` explicit and back up its
database. New setup creates a separate store; it never converts or reassigns the
historical tenant. Physical expiry cleanup needs a healthy worker, and hosted
operations still need an asset-volume capacity and orphan-file cleanup policy.
