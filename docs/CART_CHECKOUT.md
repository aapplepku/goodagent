# Cart, Checkout, and Inventory MVP

The shopping MVP connects the shopper and store-operator applications through one
tenant-scoped backend while keeping model advice separate from transaction
authority. It is a local validation system, not a production checkout.

## Authority model

| Actor | May read | May change |
| --- | --- | --- |
| Shopper model | Bounded catalog search results and shopper-approved memory | Nothing in cart, checkout, payment, order, or inventory state |
| Shopper UI/API session | Its own cart, checkout preview, and confirmation | Its own cart and explicit local test checkout commands |
| Store-operator UI | Tenant inventory summary, reservations, local orders, payment states | Nothing in this milestone |
| Commerce service | Current catalog, observed inventory, cart, reservations, payment/order records | Validated local records inside a tenant/account transaction |
| Local payment provider | Typed amount, currency, intent ID, and finite test method | Deterministic test outcome only; no external side effect |

Every command derives tenant and account identity from server-owned context. The
browser cannot submit a price, currency, stock figure, account ID, tenant ID, card
number, security code, billing address, or arbitrary payment token.

Cart add, quantity-change and remove routes carry the server-captured account-data
version into the serialized write transaction. Active identity, guest expiry,
preview scope and that version are rechecked before either receipt replay or a
mutation. A request admitted before personal-data deletion cannot add products
after deletion commits. This is an admission fence, not durable recovery of an
uncertain cart change: retrying Add after a lost response can still create a new
intent. Do not treat a cart refresh as proof that an earlier command has finished.
Reload-safe original-intent retry and cross-tab/deletion recovery remain open.

## Lifecycle

1. Adding or changing a line rechecks the active catalog, current variant price,
   and observed stock, then increments the cart version.
   Both store links and the legacy shopper entrypoint resolve chat product cards
   against catalog details and require an explicit choice for multiple variants.
2. Checkout preview requires that exact version. It revalidates all line and
   catalog versions, computes the total in integer minor units, applies the local
   policy limits, and records expiring reservations.
3. Confirmation locks the mutable state and checks that the cart and reservations
   still match. The typed local provider returns success or a controlled decline.
4. Success creates at most one immutable demo-order snapshot and marks the cart
   converted. Active reservations become consumed. The source inventory snapshot
   is never decremented or overwritten.
5. A decline keeps the checkout retryable. Cart edits or expired holds require a
   new review. Idempotent retries replay the stored result; a reused key with a
   different payload is rejected.

Terminal checkout state is also retained independently of personal request
receipts. A delayed duplicate cannot turn a succeeded checkout into a cancellation
after shopping-data deletion erases those receipts. Reading the retained success
or cancellation does not recreate the erased receipt, repeat the provider call,
or create another order. A delayed nonterminal result must still match the current
attempt's key and request fingerprint before it can change state.

The design follows the shape of a provider intent lifecycle: one intent per
checkout, explicit states, reuse across retries, and idempotent commands. Stripe's
[Payment Intents guidance](https://docs.stripe.com/payments/payment-intents),
[lifecycle documentation](https://docs.stripe.com/payments/paymentintents/lifecycle),
and [idempotent request guidance](https://docs.stripe.com/api/idempotent_requests)
are useful provider-boundary references. They do not imply a Stripe integration.
PostgreSQL's [row-lock documentation](https://www.postgresql.org/docs/17/explicit-locking.html)
informs the concurrency boundary. PCI SSC's
[tokenization guidance](https://www.pcisecuritystandards.org/faqs/1384/) reinforces
keeping primary account numbers outside this application; this MVP goes further
and has no card-data field at all.

## Demo Order History

### Interrupted confirmation

Checkout review displays the server's exact hold deadline, converted to the
shopper's local date/time with a timezone label. Reopening a review does not
promise a fresh fifteen-minute hold. An unavailable deadline requires returning
to the cart for a new review; it does not enable a new test confirmation.
The browser does not infer payment failure or mutate checkout state from its
device clock. A decline notice no longer asserts that the hold is still active;
the server revalidates reservations before any further explicit test confirmation.

The client keeps a minimal store/account-scoped attempt pointer in tab session
storage: checkout ID, cart version, hold expiry, idempotency key and test method.
No prices, cart contents or authentication secrets are stored there. After reload
or a failed confirmation response, it checks authenticated server state before
another payment action. Storage-unavailable sessions still discover current state
from the server, but cannot invent a missing original retry identity.

`GET /v1/shopper/checkout/current` discovers an account-scoped processing attempt,
including one started in another tab, but does not surface old completed orders;
`GET /v1/shopper/checkout/{checkout_id}` reads one authorized attempt. Neither
endpoint renews holds, confirms payment or changes the cart. Processing is never
displayed as failed solely because the browser lost its response. A known attempt
can use **Retry same test payment** with the original key and body; a different
key or changed body is rejected during processing. Successful responses clear the
pointer and show the persisted order. Identity change/logout clears local pointers.

Expired or cancelled non-processing checkouts require explicit fresh review.
If the no-money provider returns after its hold expired or its cart changed, the
service preserves that observed result in durable metadata and the audit log,
cancels the unusable attempt, and fences the cart version. No order is created.
The shopper can explicitly review again with a new checkout identity. The runtime
rejects providers whose declared payment mode is not `local_test`; real payment
reconciliation is not implemented and must not reuse this demo cancellation path.
Processing without a usable original pointer, or after its hold expires, stays an
unresolved checking state when no provider result was received and cannot silently
start a different payment. This
private local provider has no real money movement; automatic repair of historic
unknown attempts is not a production payment reconciliation system. Existing
processing records predating request-body fingerprints cannot be replayed under
this new guarantee; retain them for diagnosis instead of resetting their state.

### Completed orders

The shopper sidebar's **Demo orders** opens persisted checkout snapshots with
order numbers, dates, line items and totals. Reopening or reloading retrieves them
again, with older-page loading and an explicit retry on connection failure.
`GET /v1/shopper/orders?limit=20&offset=0` accepts 1-50 records per page and returns
`items`, `next_offset` and `payment_mode: local_test`. Records are newest-first,
scoped to the server-authenticated store and shopper, never a browser-supplied
account ID. This is read-only; it does not expose payments or add order mutations
to the agent. All orders are clearly labeled test checkouts, not purchases.
Ordering uses creation time descending with a descending order-ID tie-breaker.
Offset pages are not a frozen snapshot: newly created orders can move page
boundaries. The client suppresses repeated IDs; reopen the drawer to refresh the
newest page. Cursor/snapshot pagination remains a future large-history improvement.

Guest orders remain accessible only during that guest identity's lifetime.
Creating a new account preserves the identity and its orders; signing into a
different existing account does not transfer checkout audit ownership. Personal
shopping-data deletion retains checkout audit records as disclosed in the UI.

Cart-conflict sign-in shows titles, variants and quantities from both authenticated
carts. It discards only the explicitly rejected cart, never combines quantities,
and rejects a choice if a cart changed since review. Re-sign-in refreshes the
choice. Temporary guest activity and monitoring remain temporary as disclosed.
While submitting the choice, controls are disabled and a sign-in progress message
is announced. A connection failure keeps the previews visible for retry; success
is shown only after the server response.

When an open guest cart is kept while signing into a different account, its cart
version advances. Review checkout again under the signed-in account; previous
guest checkout previews and reservations are not reused or reassigned. Their audit
ownership stays with the guest. Keeping an existing account's cart does not change
its ownership, and registering the same guest identity does not transfer the cart
to a different account. Every fresh preview revalidates price and availability.

## Deliberate limits

- No real payment authorization, capture, settlement, refund, dispute, or webhook.
- No tax, shipping quote, address collection, fulfillment, cancellation, or return.
- No source inventory adjustment, allocation across locations, backorder, or
  warehouse write.
- No promotion-code or personalized-price application during checkout.
- No model tool can perform a commerce command.
- Local identity and policy limits are demonstration controls, not production
  fraud prevention, compliance, or authentication.

A future live provider must remain behind the typed payment interface and add
signed webhook verification, durable uncertain-outcome reconciliation, external
provider receipts, production authentication, fraud controls, tax/shipping rules,
and an independently reviewed PCI scope. A future inventory provider must retain
preconditions, idempotency, policy, audit, and rollback metadata and must not be
introduced by simply writing observed snapshot quantities.
