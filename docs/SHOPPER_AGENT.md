# Conversational shopper agent

New stores now use [guest-first self-service shopping](SELF_SERVICE_SETUP.md).
The account-first root entrypoint below is retained for explicit legacy demos.
Store links at `/s/{slug}` support guests, optional account continuity, temporary
versus durable memory, explicit variant selection, and scoped private previews.

The shopper experience is a separate Next.js application at `http://localhost:3001`.
It shares the manager-owned tenant catalog and search index through typed backend
services. It does not share manager conversations, memories, status tools, code
context, or operating permissions.

Model requests use the shared provider's configured elapsed request/body deadline
as well as individual connection/read timeouts. A slowly trickling response ends
with an unavailable-model result and releases local request capacity; browsing
remains available. An uncertain provider outcome keeps its conservative usage
charge. A browser disconnect or local timeout does not promise provider-side
cancellation or a billing reversal. No automatic paid retry is added by recovery.

## Accounts and memory

Self-service stores register by upgrading an authenticated guest and issue a
single-use recovery code. The legacy-demo direct-registration route predates
recovery codes and does not provide that recovery flow. Sign-in preserves the
guest visit's conversations and preferences, with disclosure before submission;
cart conflicts require a separate explicit choice. Guest activity logs and personal
monitoring rules remain temporary: signing into an existing account discards them,
as disclosed before sign-in and again before confirming a cart conflict. They are
not migrated into the registered account; its existing monitoring rules are retained.
The cart review lists both carts before **Keep this visit's cart** or **Keep account
cart** is selected. Neither choice is preselected. **Back to sign in** leaves both
carts unchanged; a failed request keeps the review available for retry.
Expired guest cookies are
ignored for credentialed sign-in, not treated as proof of identity or merged.

Password recovery invalidates earlier pending authentication, not just existing
sessions. Before admitting a login or transferring guest progress, the server
rechecks the credentials under the same write lock used by recovery. Cart-choice
permissions are bound privately to the target account's credential state, as well
as their existing guest/store/cart versions. After recovery, sign in again to
review the carts; an old prompt makes no transfer. Missing or malformed older
bindings fail closed. No credential hash or binding is returned to the browser.
If the cart-choice permission has expired but the original guest session remains
valid, the account panel keeps the visit open and offers **Back to sign in**. It
checks only that bound guest, never discovers a replacement account or retries
the merge automatically. A changed or expired guest still enters session recovery.
Normal sign-out revokes sessions but does not rotate credentials or promise to
cancel all already-authorized work.

The local demo uses username accounts so it does not need an email address. Passwords
are salted and slow-hashed with scrypt. The browser receives an opaque, HttpOnly,
SameSite=Strict session cookie; PostgreSQL stores only its SHA-256 hash. Sessions
expire after seven days by default and are revoked on sign-out.
Self-service guest accounts and their sessions instead expire after 24 hours.
Guest preferences are temporary; registering preserves the existing account's
progress. Account controls provide session management, recovery and explicit
shopping-data deletion. Turning shopping memory off disables both saving and
recall without deleting previously saved preferences. The authenticated memory-list
endpoint still returns retained preferences for inspection and individual deletion
while memory is off. Management access does not enable model recall or saving.
Opening Account moves keyboard focus into the panel; Escape closes it and returns
focus to its opener. Shopping-data deletion requires a separate confirmation,
shows progress while waiting, and reports completion only after the server succeeds.
A failed deletion remains retryable. Demo checkout audit records are retained.

Deletion and guest retirement advance an internal persisted account version under
the tenant write lock. Agent monitoring tools and API activity instrumentation
retain their original server-owned version; later personal writes reject a stale
version, expired identity or retired guest. Personal monitoring receipts are erased
as well, so an old turn cannot recreate a monitor or acknowledge a deleted rule.
Fresh authorized work still functions after deletion. This does not recall context
already sent to a provider, reverse previously committed work or cancel every kind
of accepted commerce action. Guest quota and memory opt-out receipts stay intact.
Expiry cleanup separately revalidates active guest status and current expiry after
acquiring that lock, before any deletion. A stale cleanup selection cannot erase
an account whose registration already committed, or retire the same guest twice.
An upgrade starting after expiry remains denied; this is not an expiry extension.

Merging a guest into an existing account transfers conversation and preference
records, then erases the retired guest's exact chat, chat-start, memory-save and
memory-delete response receipts in the same transaction. Those duplicate response
copies are not transferred. Guest quota, memory-setting and commerce receipts are
retained; a failed merge rolls the transfer and erasure back together.

The worker's existing cleanup also revisits disabled guest accounts with outstanding
content receipts, rechecking tenant and retired-guest eligibility under the write
lock. Each pass selects at most 100 such accounts and excludes already-cleared
accounts so subsequent passes progress. This is an account-count limit, not a hard
receipt-row or execution-time limit. Historical copies in an existing installation
remain until the updated worker is deployed and cleanup runs. Local regression
work does not execute that repair against original stores. Backups retain their
independent retention lifecycle.

A protected request returning HTTP 401 replaces the private shopper interface with
session recovery and fences outstanding responses from the former session. Sign in,
use a registered account's recovery code, or use **Check session** after opening a
visit or signing in elsewhere. Only the same server-verified
account in the same store can recover its in-memory draft and failed chat request.
A different account or store discards that local text. Unsent text is not written
to browser storage and does not survive reload. An expired public-store visit can
explicitly **Start a new guest visit**; its old temporary progress does not transfer.
Private previews do not offer that action. Wrong credentials, ordinary HTTP 403
and service failures do not silently create a new guest. Store-wide access denial
uses HTTP 404 with `STORE_UNAVAILABLE`, separately from account expiry and missing
individual resources; it closes the store view without deleting session/cart data.

If a chat response is lost, the failed request remains visible without overwriting
newer composer edits. **Retry same request** reuses its exact original payload and
idempotency key; **Dismiss failed request** allows a new send but does not cancel
server work that may already have completed. No automatic chat retry runs. The
failed request and newer draft are kept separately until recovery or dismissal.
The current shopper UI includes its issuing `expected_account_id` in every new
chat request and retry. The API and service compare it with the authenticated
account before chat writes or model execution. It is a precondition, never a way
to select an identity. Changing the cookie in another tab therefore cannot replay
that retained request into a different account. The field is optional for older
clients, which lack this added safeguard. It is not included in command hashes;
account-scoped existing receipts remain compatible, and the precondition is checked
before replay. A reply arriving after navigation updates history without switching
the active conversation or redirecting the new draft.
Existing scoped checkout and memory-change receipts survive session recovery;
checking checkout status is read-only, and neither payment nor memory changes are
automatically repeated. These controls do not bypass server authorization.

Account protection also covers non-chat actions. The current client binds protected
requests to the account shown when the action or retry was created. If another tab
signs into a different account in the same store, the server rejects the old view's
request before cart changes, preference saves, deletion, session revocation or
receipt replay. Protected reads cannot load the replacement account's data under
the old account label. Recovery requires an explicit session check or sign-in;
it never retries the old action as the replacement account. Guest upgrade/sign-in
from a live view also checks which guest's progress would be imported.

This check uses `X-Shopper-Account-Id` as an expectation, not authorization. Cookies
and server-side store/account checks remain authoritative. Older clients without
the header lack this extra protection; update both API and shopper client. Actions
already accepted before a later account switch can finish for their originally
authenticated account. There is no cross-tab cancellation or automatic replay.
In particular, an already accepted logout response can clear a newer same-store
cookie when it arrives; the header does not serialize browser cookie updates.
**Start a new guest visit** additionally requires the server's committed `created`
flag. If a valid guest appeared in another tab during recovery, it is not presented
as a newly created visit. Recovery stays visible and **Check session** remains an
explicit choice; a local conflict message points to that action. Existing guest
progress and the new cookie are not deleted. Genuine connection failures retain a
generic retry message, without disclosing another account's identity.

Public-store session recovery also offers **Use a recovery code** for an existing
registered account. Recovery rotates the password and single-use code. The client
keeps the returned replacement code in memory, verifies that same account, and
waits for explicit acknowledgment before returning to shopping. An interrupted
verification retries only the account read, never password recovery. Continuing
rechecks the identity; a changed account discards the code and cannot inherit the
old draft. The code is not saved in browser storage: reloading or leaving the page
loses it. If the recovery response itself is lost, use **Check session** or sign in
with the chosen new password; recovery may already have completed. No replacement
code delivery is claimed without the response. Private previews and the legacy
demo entrypoint do not expose this registered-account recovery path.

Private-preview recovery requests are also rejected by the service before password
hashing, code rotation or session revocation. Open the shared store to recover a
registered account. Newly issued registered sessions, including guest upgrades,
sign-in and recovery, use `OPEN_COMMERCE_SHOPPER_SESSION_DAYS` (default seven;
one to thirty days) for persisted expiration as well as the browser cookie.
Guest sessions still expire with their temporary account after 24 hours. Changing
the setting does not rewrite existing sessions; revoke them explicitly through
the account's session controls when required. Deploy updated source for the fix;
no database migration or automatic revocation is performed.

A current public-store guest can also choose **Save your progress -> Recover**.
This opens the same parent-owned receipt flow before credentials are submitted;
switching from the guest to the recovered account cannot close a drawer and lose
its replacement code. The heading distinguishes requested recovery from expiry.
Requested recovery is code-only, without an ordinary sign-in or new-guest shortcut.
It does not merge guest conversations, preferences or carts into the recovered
account. To use ordinary sign-in and its transfer choices, choose **Return to
current visit**, verify the current session, then use the normal account panel.
Before recovery is submitted, this check restores the same guest's unsent text
only when that guest is still authenticated. After a successful recovery changes
the session, it cannot promise access to the former guest. Voluntary entry is
blocked during pending account, memory, chat or cart actions; it never claims to
cancel an already-issued server request. Receipt loss on reload/navigation and
explicit verification/retry limits are the same as the expired-session flow.

Discovery reports `conversation_mode` separately from catalog readiness. `basic`
means the service has no model provider and uses its deterministic search path;
`model_configured` means the model-backed path is selected, even if its credentials
or connection later fail. It is not a successful connectivity probe. `unknown`
is the compatible default for absent/older state and does not imply AI readiness.
The welcome and composer set those expectations before a first message; no provider
call is made by the discovery endpoint.

A store-specific welcome uses only its existing catalog-derived starter controls,
not a strip of unrelated sample merchandise. Their optional thumbnails use that
store's ingested, authorized image URLs without public image optimization or a
referrer. Missing, rejected or failed images leave usable text controls; an image
failure does not trigger another catalog query or substitute a different product.
These are category representatives, not personalized recommendations or proof of
search quality. A verified sample-store flag retains the applicable ABO credits;
ordinary merchant images do not inherit that attribution. The separate legacy
sign-in/welcome retains its explicitly labeled bundled sample artwork.

Conversations, messages, and shopping preferences survive sign-out and sign-in.
With the hosted model enabled, the model chooses when to call `save_shopping_memory`.
There is no preference-keyword intercept in the hosted conversation. Statements such as
`i am into organic stuffs` can be saved without a separate remember command; a turn can
save and search, or just chat. The prompt distinguishes ongoing personal preferences from
temporary queries, third-party preferences, hypothetical statements, and explicit opt-outs.
Intent selection is model-based and is not a guarantee of perfect semantic classification.

The tool accepts only a source message ID and a bounded exact preference quote. The
application validates Pydantic arguments, shopper-authored provenance, tenant/account
ownership, privacy checks, explicit opt-outs, and a three-save turn bound. Assistant and
catalog text are never eligible sources. It stores the shopper's words, not an inferred
profile or model paraphrase. The user message commits before tools run; each save commits
with an idempotent receipt before the model sees success. Repeated identical saves reuse
memory. Replaying a tool receipt cannot resurrect a memory removed through the drawer.
Saves recheck account expiry and memory permission at persistence time. Completing
or replaying a chat response rechecks its saved-memory receipts against current
account state; a removed or disabled preference cannot be returned as a new save.
The drawer refreshes from current server state rather than merging old chat receipts,
and ignores reads that overlap a completed deletion. A changed-memory response asks
for a fresh turn rather than claiming that the old preference was restored.
Opening the drawer refreshes the authenticated management list, including retained
preferences while memory is off. If an individual removal response is lost,
**Retry removal** reuses its original account/store-scoped idempotency key; it
never retries automatically or treats an authorization failure as success. In-flight
duplicate removals are disabled. An explicit session recovery retains an uncertain
removal only for the same verified account and store. These removal receipts live
in memory only: reload loses the retry control, then the current list is fetched
again. Signing out, changing account/store or deleting shopping data clears them.
Deleting a preference does not erase its original conversation text; use shopping-data
deletion to remove conversations as well. Disabling memory prevents preference-store
recall, but does not retroactively unsend context already provided to a running model.
For both guests and registered accounts, a disabled setting supplies disabled-memory
instructions, excludes saved preferences from recall, and hides the save tool. Only
enabled guests receive temporary-visit memory instructions; enabled registered accounts
receive persistent-account instructions. Stored preferences remain available for
authenticated inspection and explicit deletion while memory is off.
Memory-setting changes remain serialized even when Account is closed and reopened.
If a response is lost, the setting is shown as unverified and chat pauses while
browsing remains available. **Retry memory change** reuses the same account-scoped
idempotency key, including after a tab reload; it cannot replay an old change over
a newer setting. Tab storage must be available before sending the change. Minimal
boolean setting receipts are retained when shopping data is deleted so delayed
retries cannot undo opt-out; they contain no conversation or preference text.
The **Saved to shopping memory** badge and `memories_saved` response list come from actual
committed saves; `memory_created` remains as a compatible first-memory field. Later model
failure retains successful saves and reports the incomplete reply. New chats recall up to
12 of the account's latest 20 preferences. The existing explicit-phrase extractor remains
only for the deterministic offline demo, with its intentionally narrower vocabulary.
Old history is not silently backfilled: send `save that preference` in the same
conversation or restate it once after updating. Memories
can be reviewed and deleted in the Shopping memory drawer. Every identity, session,
conversation, message, and memory query is scoped by both `tenant_id` and the
authenticated account where applicable.

This identity implementation is for the experimental self-hosted alpha; it is not
a qualified public hosted service. Do not enter
names, email addresses, phone numbers, delivery addresses, credentials, secrets,
or other personal data. Direct contact and secret-like input is rejected before a
model call.

## Search loop

Model-backed shopper turns now finish with a typed `complete_shopping_turn` tool.
The provider requires a tool decision, but the model still chooses whether to chat,
ask a necessary question, investigate, or finish. Completed catalog answers require
a successful search/lookup receipt and a successful final card selection (which may
be empty); price-comparison completion additionally requires a successful arithmetic
receipt after the latest search/lookup. A newer failed comparison supersedes an old
success. Selected comparison cards must be a nonempty subset of the last compared
product IDs; recommending only the cheaper item remains valid.
Catalog and price-comparison completions must explicitly declare `product_ids` in
the same order as the latest successful selection. Missing, duplicate, malformed
or mismatched IDs are rejected; the model must reselect cards before trying again.
Other completion kinds declare `null` and return no product cards, even if earlier
operations selected some. The model is instructed to review returned descriptions
and remove unsuitable items before declaring its final selection.
Memory and activity completion require their corresponding receipts. Blocked replies
must reference an observed tool failure. An explicit `refusal` can decline unsupported
or unauthorized work before or after read-only investigation, without attempting a
forbidden action to manufacture a failure. It must declare `product_ids=null` and
never returns product cards. Refusal is a model-declared disposition, not proof that
the refusal was semantically appropriate; it does not undo already committed saves.
Invalid completion returns a correction to
the same bounded loop; raw final-answer prose alone cannot end it successfully.
Corrections name the appropriate completion kind and card declaration. A successful
empty result or missing variant is catalog work, not a tool failure; no extra lookup
is required simply to correct a completion category. Selection receipts also explain
how to finish. Existing iteration and tool limits are unchanged.
The completion control performs no write and uses the existing model-turn budget,
not the action-tool allowance. The operator's default tool choice is unchanged.
These checks validate declared completion against execution evidence. Product-bearing
catalog and comparison drafts additionally receive a separate read-only model review
before display. It receives the bounded conversation, explicit preferences, proposed
answer/cards and current catalog receipts. It has only a typed verdict tool, no
shopping or memory tools, and cannot change the draft. Its verdict must bind the exact
candidate snapshot and ordered product IDs. Mismatched, malformed, incomplete,
unavailable or rejected review cannot publish the draft or cards. The acting agent
can correct a rejected draft within its remaining budget; otherwise the shopper sees
an honest incomplete response while committed memory remains intact.

Review requests use the same configured provider, authenticated usage admission,
output cap and total per-turn request limit as the acting agent. They increase average
latency and quota consumption without raising those ceilings. Oversize review context
is rejected, not silently truncated. Ordinary chat, memory-only and no-card completions
do not request this extra review. Only bounded operational summaries are visible;
private reasoning and rejected drafts are not shown.

This is a model judgment, not an independent factual or semantic guarantee. The same
model can make correlated errors, and no-card prose is outside this additional gate.
Typed output constrains structure, not correctness; see the official
[Structured Outputs guidance](https://developers.openai.com/api/docs/guides/structured-outputs).
A bounded synthetic live test searched successfully but claimed to exclude an item
that remained selected. The stricter final-ID declaration has offline regression
coverage. Two subsequent bounded real-model evaluations both failed qualification:
one displayed ordinary glassware for an impossible requirement despite denying the
requested property, and both exposed completion-category retry loops. Exact price
comparisons and budget discovery succeeded in that small sample. More specific
completion feedback, explicit refusals and the separate answer review were then
exercised in two new bounded runs: four tests passed per run, 59 model requests
total. Independent evidence review found no actionable issue in the eight tested
adversarial outputs. Human narrative approval remains pending; earlier failures
are retained. Even matching IDs cannot
prove that freeform prose describes suitability correctly. Semantic relevance and
accepted browser recordings remain release gates.

The shopper agent has bounded read-only catalog search, authoritative product lookup,
price comparison, explicit result selection, and the account-scoped
`save_shopping_memory` tool. With the hosted provider enabled, it may perform up to three
sequential searches to decompose or
refine a complex request. Tool arguments are strictly validated, the server supplies
the tenant, catalog fields are treated as untrusted data, and the answer may show
only explicitly selected products observed in tool results. Product lookup can
read an exact product ID supplied by the shopper without requiring a prior search.
Discovery search requires `in_stock=true` because its serving path only selects
available variants; catalog browsing and product details retain unavailable items.
Named comparisons can
look up separate short product names rather than submitting the entire comparison
as one search. Product lookup reads the server-authorized catalog version and actual
variants; missing attributes remain unknown. Price comparison requires an observed
product ID and, for multi-variant products, an explicit variant ID validated against
the freshly read authorized catalog. Prior observation of that particular variant
is not enforced; looking it up first is model guidance. The comparison computes
same-currency differences in integer minor units. It does not infer variants or
include tax, shipping, or discounts.
Comparison references are deduplicated after resolving the actual variant, so
implicit and explicit references to the same variant cannot count as two items.
Before selecting cards after a comparison, every compared variant is re-read,
including unselected counterparts. Changed prices/currencies, missing variants or
unavailable reads require a fresh comparison and selection. Cards use an actual
compared variant, not an unrelated representative price. The tool receipt identifies
that variant; the current UI still shows one card per product, not one per compared
variant. This does not reserve prices or provide an atomic snapshot across products;
availability, suitability and freeform prose are separate concerns.

`select_catalog_products` re-reads selected products before returning their cards.
Its model-facing receipt also includes up to 1,000 redacted characters of each
selected product's current description. This provides catalog evidence for feature
statements without treating search highlights as proof. Missing attributes remain
unknown, and catalog descriptions remain untrusted claims, not independent testing.
Selection receipts also include the chosen variant's current options and availability
and up to 12 current variants for each selected product, with explicit truncation
and withholding flags. This preserves facts needed for separate-product lookups
without reusing stale variant lists. Without an authoritative reader those fields
remain unknown; previous search hits do not manufacture fresh stock or variant evidence.
Each later search, lookup or comparison clears that selection. A failed model turn
does not automatically promote every retrieved hit to a recommendation. Follow-ups
receive prior card IDs and must re-read current facts rather than relying on old
prices. These checks enforce IDs, catalog scope and arithmetic, not perfect semantic
relevance or guaranteed factual prose; real-model quality evaluation remains required.

The interface exposes short operational
summaries under **How I searched**, never private chain-of-thought. While a turn
is running, the shopper message appears immediately and the interface shows an
elapsed waiting time, not invented tool phases or model reasoning tokens.

Server-side model diagnostics record only response status, output-type/phase counts,
allowlisted tool names and numeric token usage. They do not record model text, tool
arguments, prompts, credentials or opaque reasoning continuation. These structural
events help diagnose premature replies; they do not establish answer quality or
successful execution of a requested action.

Synthetic evaluation wrappers can opt into a local completion-result observer. It
records actual accepted/rejected completion decisions even when no next model call
occurs. Accepted receipts contain the kind and final card IDs, not answer text or
private reasoning. Normal providers do not install this observer; it adds no model
request or persistent production logging. Evaluation verifies the receipt against
the issued call and visible reply rather than treating a tool request as success.

Assistant Markdown renders emphasis, lists and code. Raw HTML, embedded images and
unsafe link schemes are disabled. Shopper-authored text remains literal.

An unfinished or failed model turn cannot execute a new tool, including a memory
save or monitoring rule. Valid-looking arguments alone are not proof the request
finished. Responses must explicitly report their status; missing status is never
assumed to mean completed. Incomplete message-only, reasoning-only and empty
responses are also rejected before checkpointing. Malformed calls and multiple calls in the sequential
protocol are rejected before their output can enter a saved continuation.
Completed results from earlier turns remain available; the reply reports
unfinished work without inventing a successful save or a product recommendation.
Cards selected during the current turn are provisional until typed completion is
accepted. Model failure, rejected completion, and iteration or tool-budget exhaustion
return no new product cards and do not list those provisional products in fallback
text. Previously committed memory saves remain visible; they are not undone by a
later reply failure. This does not validate the meaning of an accepted model answer.

Without a model credential, deterministic mode searches the complete request once
and returns grounded ranked options or an honest clarification, or handles a narrow
explicit preference. If a configured provider fails before producing results, the response
states that automatic preference saving did not run, retains the message, and offers
browsing without substituting unselected search hits. Source product or variant IDs
that resemble credentials or direct contact details are withheld from model tools,
not replaced with colliding redacted IDs. Such products remain accessible through
ordinary authorized browsing. Variant availability reflects source stock minus active
local holds; unknown stock is not presented as available. Manager catalog
uploads become eligible for private preview only after the durable worker has
verified their Qdrant index. In self-service stores, the owner must explicitly
publish that exact catalog version before ordinary guests can search it. Indexing
a replacement alone does not replace the previously published catalog.

`GET /v1/shopper/discovery` supplies the empty-state suggestions. It returns up to
six representative in-stock categories and products from that same active tenant
catalog and refreshes while the signed-in app remains open. A suggestion click sends
its catalog-grounded query immediately. No static product suggestion is presented as
store inventory when the catalog is not ready.

No shopper model tool can add to a cart, check out, order, reserve inventory,
change price, apply a promotion, or write commerce state. Search results expose
explicit **Add** controls owned by application code. The cart and checkout APIs
are separate authenticated command paths; an agent response can recommend a
product but cannot submit those commands.

## Cart and test checkout

Operational logs and chat-configurable monitoring are documented in
[Shopper activity](SHOPPER_ACTIVITY.md). The shopper sees its own redacted events; the
operator can inspect store-wide activity without viewing private conversation or memory text.

**Browse catalog** works for guests and registered shoppers within their store
link; `/catalog` remains the legacy-demo entrypoint. It displays the same authorized
catalog version as conversational search, with images, category/text/stock filters,
price sorting and paging. When filters return no matches, **Clear filters** resets
the text, category, stock filter and page without changing the sort order. Ready
catalogs refresh every 30 seconds; pending indexing is polled every five seconds. Ordinary guests
continue seeing the published catalog until the owner explicitly shares a verified
replacement; a private preview is limited to its granted catalog version.
Changing filters or manually refreshing retains the previous cards while showing
**Updating results**. A failed request labels them **Previous results** and offers
the existing refresh control; it does not claim that old products match the new
filter. Counts describe the current result only after a successful response.
Product cards expose explicit add-to-cart and assistant-comparison actions;
unconfirmed or exhausted availability disables adding. The cart server still
revalidates all facts before accepting a command.

Each guest or registered account has at most one open tenant-scoped cart. For a
multi-variant product, the shopper must explicitly select a variant in product
details before adding it. The server validates that choice against the authorized
catalog and reads the title, image, price, currency and availability; the browser
cannot submit price or inventory facts. Every cart
mutation requires an idempotency key and increments a version.

Checkout is intentionally two-step. **Review checkout** validates the exact cart
version against current catalog and inventory state, records a bounded policy
decision, and creates expiring local holds. **Approve test payment** confirms a
deterministic local payment intent and creates one durable demo order; **Test
decline** exercises the retry path. The API accepts only `test_success` and
`test_decline`, never a card number, security code, billing address, or arbitrary
payment token. No real money moves.

Reservations are an application-owned concurrency ledger. They reduce displayed
sellable quantity and become consumed on demo order creation, but they never
decrement or overwrite the manager-owned source inventory snapshot. There is no
shipping, tax, refund, cancellation, fulfillment, or live-provider integration.
See [Cart and checkout design](CART_CHECKOUT.md).

## API

```text
POST   /v1/shopper/auth/register
POST   /v1/shopper/auth/guest
POST   /v1/shopper/auth/login
POST   /v1/shopper/auth/merge
POST   /v1/shopper/auth/recover
POST   /v1/shopper/auth/logout
GET    /v1/shopper/auth/sessions
DELETE /v1/shopper/auth/sessions
PATCH  /v1/shopper/preferences
DELETE /v1/shopper/shopping-data
GET    /v1/shopper/me
GET    /v1/shopper/conversations
GET    /v1/shopper/conversations/{conversation_id}
GET    /v1/shopper/memories
GET    /v1/shopper/discovery
GET    /v1/shopper/catalog
DELETE /v1/shopper/memories/{memory_id}
POST   /v1/shopper/chat
GET    /v1/shopper/cart
POST   /v1/shopper/cart/items
PATCH  /v1/shopper/cart/items/{line_id}
DELETE /v1/shopper/cart/items/{line_id}
POST   /v1/shopper/checkout/preview
POST   /v1/shopper/checkout/confirm
GET    /v1/shopper/checkout/current
GET    /v1/shopper/checkout/{checkout_id}
GET    /v1/shopper/orders
```

Chat, memory deletion, cart changes, and checkout operations require
`Idempotency-Key`. The shopper web app uses an allowlisted same-origin proxy,
including store discovery, authorized assets and shopper activity endpoints. It
forwards store-scoped shopper/preview sessions, never the merchant session. The
server resolves store publication or preview grants and validates account scope;
a store slug is not permission to access private merchant or shopper data.
