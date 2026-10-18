# Self-Hosted Alpha Threat Model

## Scope And Assets

This describes the current experimental owner/shopper application, not a security
qualification. Use non-sensitive test data on a trusted workstation. Assets include
store identities, catalogs, unpublished previews, conversations, shopping memory,
demo carts/orders, model budgets, credentials and durable jobs. There are no real
payments, fulfillment or source inventory writes. The older simulator is a separate
compatibility mode; its frozen release evidence does not qualify this application.

| Profile | Identity and deployment boundary |
| --- | --- |
| `self_hosted` | Console-issued first-owner setup, local accounts and authenticated store membership. Compose binds to loopback. |
| `hosted` | Configured OIDC issuer/subject identity, authenticated membership, exact origins and deployment-wide model ceilings. This adapter is tested with a controlled fixture, not a qualified hosted service. |
| `legacy_demo` | Implicit local tenant/roles for the historical simulator and existing demo. Not authentication; never expose to an untrusted network. |

A database administrator, Docker-socket holder or host-file owner is trusted and
can bypass application controls. These controls do not protect against a compromised
host, hostile local administrator or malicious extension. HTTPS termination,
internet exposure, provider configuration and operational security need separate
qualification before any hosted deployment. Do not use a public tunnel for this alpha.

## Trust Boundaries

| Boundary | Threat | Current controls | Residual limits |
| --- | --- | --- | --- |
| Browser to app/API | Cross-site actions, forged store IDs, session theft | Host/origin checks, same-origin proxies, nonce CSP, separate opaque HttpOnly merchant/shopper cookies and server-side authorization | Loopback HTTP is not transport encryption; endpoint limits are per process |
| Owner login | Account takeover or identity confusion | Hashed credentials, bounded login attempts, one-use recovery codes; hosted identity binds verified issuer and subject, not an email match | Console access is trusted; eventual hosted provider configuration still needs verification |
| Shopper or preview session | Cross-store access or preview privilege escalation | Store-scoped session validation, short-lived store/catalog preview grants, explicit sharing checks; preview grants carry no merchant membership | Expiration and revocation depend on server state; browser possession remains a bearer credential |
| PostgreSQL records | Cross-tenant access, duplicate effects | Tenant/account predicates, composite constraints, transactional idempotency and permission checks | Application scoping is not a production RLS or database-owner isolation claim |
| CSV and catalog text | Parser exhaustion, prompt injection, malicious content, stale-tab confirmation | Bounded streamed upload, typed mapping/row validation, encrypted temporary staging, confirmation bound to the exact reviewed upload/mapping/currency under the tenant write lock, and separate versioned publication | Catalog content remains untrusted; validation does not establish product truth or legal rights; older clients must refresh their review |
| Remote product images | SSRF, decompression exhaustion, tracking | Public HTTPS-only destinations, DNS/address checks, pinned connections, no redirects, size/dimension/time bounds, raster re-encoding | DNS/network/image libraries remain dependencies; failed images are reported separately |
| Model request/result | Secret leakage, invented claims or unauthorized action | Typed providers, bounded context, redaction, validated tool arguments/results, server-resolved ownership and authoritative product services | Redaction and model instructions are not complete privacy or grounding guarantees |
| Qdrant result | Forged/stale payload or irrelevant match | Tenant/catalog-version filters and authoritative catalog validation | A ready index is not evidence of retrieval quality; Qdrant is a rebuildable projection |
| Background delivery | Lost, duplicate or interrupted work | Persisted ownership, durable jobs/receipts, leases and checkpoint recovery | Redis or worker recovery is not instantaneous; expiry and failed jobs need monitoring |
| Cart and demo checkout | Implicit purchases, price drift or duplicate order | Explicit UI/API actions, authoritative variants/prices, reservation checks and idempotent demo outcomes | No payment, tax, shipping or fulfillment integration; outcomes are not revenue |
| Logs and memory | PII leakage, false save claims, unwanted recall | Tested redaction, scoped operational events, committed memory receipts, account saving/recall toggle and deletion controls | Avoid sensitive data; backups may retain deleted data until their own retention expires |
| Dependencies/images | Vulnerable bundled or native components | Lockfiles, raw scans, SBOMs, exact-image review, non-root users, dropped capabilities and no-new-privileges | Scanners have coverage gaps; missing or expired applicability evidence blocks qualification |

## Identity And Publication

Owner APIs resolve an authenticated membership, not a model-selected or browser-
supplied tenant ID. The explicit legacy profile is the exception described above.
Store discovery resolves a slug before shopper authorization; discovery is not a
merchant grant. Private preview sessions authorize only their store and catalog.
Public shopper access requires enabled sharing, and disabling sharing blocks guest
access. Publishing selects an exact verified, reviewed catalog version.

Guest sessions and temporary preferences expire after 24 hours. Optional account
upgrade preserves progress; signing into an existing account requires cart-conflict
review rather than silently adding quantities. Registered memory has a persistent
saving/recall toggle and explicit deletion. Temporary guest context must not be
presented as durable account memory. Cookie separation does not remove the need for
server-side authorization on every route, asset, cache and job.

First-party shopper operations carry an immutable expected-account precondition;
owner operations carry an expected-owner/store pair. They are checked against the
current authenticated session before scoped work, preventing a stale tab's command
from silently targeting a different session. They confer no permissions. Explicit
session recovery does not replay the prior identity's work; older clients omitting
the headers do not have this safeguard. Browser cookie updates are not serialized,
and an already-accepted request may finish for its original authenticated identity.

Local password recovery serializes with authentication admission. Owner login
copies credential state before verification, then locks and checks the current
record before issuing a session. Shopper login rechecks the verified credential
under the tenant write lock before any cart-continuity operation or session.
Pending shopper merge grants carry an internal credential-state fingerprint,
checked under that lock before transfer; missing or stale bindings require fresh
sign-in. A login/merge committed first is revoked by subsequent recovery; recovery
committed first rejects stale authentication. Expensive password verification does
not hold the owner row lock. This is not universal cancellation of accepted data
operations or serialization of browser cookie delivery. Console code rotation
does not change the owner's password; normal session revocation does not rotate
credentials. Hosted-provider recovery remains the provider's responsibility.

Personal activity writers also compare an internally captured account version
inside the tenant write transaction. Shopping-data deletion and guest retirement
advance that version and erase personal monitoring receipts, fencing delayed agent
and telemetry writes. This does not revoke data already sent to a provider, erase
checkout audit records, or provide universal cancellation of accepted operations.
Background expiry selection is only a candidate list: guest/active/expiry state
is rechecked under the write lock before erasure or session revocation. This
preserves registration committed after selection and makes duplicate retirement
no-ops; it does not allow an already-expired guest to start registration.

Guest merge erases exact source-account chat/start and preference save/delete
response receipts in the same transaction as the history transfer. It preserves
commerce, quota and memory-setting receipts; it does not move stale replay responses
to the destination identity. A separate historical cleanup pass selects only
disabled guests with outstanding content receipts and rechecks eligibility under
the tenant write lock. Its 100-account batch is not a bound on receipt rows or lock
duration. Historical repair requires deploying the updated worker; it does not
erase backups, provider-held context or retained commerce/audit records.

See `api/context.py`, `stores/auth.py`, `stores/shoppers.py`, `stores/setup.py` and
the two clients' `runtime-proxy.ts` implementations for the corresponding boundaries.

## Model And Tool Data Flow

Unlike the old simulator, the current application can send bounded conversation,
preference and catalog/tool context to an external OpenAI provider when configured.
The provider credential is used server-side for authentication, not inserted into
model context. Raw uploaded datasets, account credentials and private customer
contact/address fields must not enter that context. Redaction covers tested patterns,
not every possible identifier; do not enter sensitive personal or business data.

Model output and catalog text are untrusted. The model cannot select a tenant,
grant permissions, publish a catalog, execute arbitrary commands, or directly
perform a commerce write. Operator tools are finite and typed. Local process
recovery, when explicitly enabled in self-hosted development, targets owned service
identifiers through a separate supervisor; it is disabled in hosted mode. Scheduled
status checks are observational, not permission to repair infrastructure.

Shopper tools can search, retrieve authoritative product/variant details, compare
integer prices and propose validated cards. Cart and checkout require explicit
user controls. Model-selected memory saves require validated input and a committed
receipt before the UI reports success. Private chain-of-thought is not exposed;
visible progress consists of bounded operational summaries and tool activity.

Configured model credentials do not prove connectivity. Successful test calls do
not prove general answer quality. Deterministic no-key replies are limited test
behavior, not a connected model. Unsupported claims, prompt injection and ambiguous
requests remain evaluation targets.

## HTTP And Resource Controls

Default JSON body limits are 64 KiB, headers 16 KiB and query strings 4 KiB.
Catalog import is a separate authenticated streaming endpoint: at most 20 MiB,
10,000 rows and 64 columns, with bounded reads. Dataset endpoints have their own
configured bounds. Image ingestion separately bounds bytes and decoded dimensions.
API/proxy limits both matter; a browser upload control is not enforcement.

Default API admission limits are 120 write-like requests per minute. Selected
expensive routes additionally have a 30-per-minute limit and a two-handler
concurrency limit; this is not a ceiling on every API/model operation. For example,
the owner AI-connection check is outside that expensive-route predicate. These are
per-process controls, not distributed denial-of-service protection. PostgreSQL model-usage
reservations are shared across API/workers for non-legacy profiles. Guest allowance
defaults to ten AI turns per 24 hours; store/deployment limits and individual run
budgets also apply. Token estimates are not a provider billing guarantee.

Production browser scripts use nonce CSP without eval; development tooling may
differ. Existing inline style attributes remain allowed. Proxies allowlist routes,
cookies and headers rather than forwarding arbitrary destinations or credentials.
Authenticated responses must not be treated as public cache entries.

Catalog images retain the API's authorization and `no-store` response on each
request. The operator disables Next.js image optimization globally; the shopper
optimizer allows only Next.js's generated static-media namespace for bundled
attributed sample photos. Next normalizes
some URL aliases; routing tests verify they cannot reach the API. Catalog/API
paths and remote URLs are not eligible for the
optimizer's public cache, including after sharing is revoked. This does not erase
copies a shopper already downloaded while access was allowed. Deployments with
older application versions must restart on the updated build; old intermediary
or browser caches are not remotely recalled by a server-side authorization change.

## Backup And Recovery

The console-only backup helper stops writers and captures all persistent volumes,
private configuration and exact image identities. Owner-only file permissions are
not backup encryption: copies include sensitive state and require private storage.
Hashes detect corruption, not malicious alteration. Restore only trusted backups.

Recovery uses a fresh project and volumes; it does not overwrite an existing store.
The default recovery network is isolated and model credentials are disabled.
Explicit local-preview mode permits outbound networking to support browser testing;
it is not equivalent to offline isolation. Restored sessions, deleted records,
queued jobs and old credentials can reappear from a historical backup. Fence the
old installation and review revocation, expiry and pending work before cutover.
See [backup and recovery](BACKUP_RESTORE.md) for the tested scope and procedure.

## Historical Simulator And Remaining Gates

Simulator writes retain typed compilation, policy/precondition checks, exact-hash
approval where required, idempotency, audit and reconciliation. A kill switch blocks
new dispatch, not reads or authorized rollback, and does not undo previous effects.
These controls do not establish remote-provider atomicity or causal sales lift.

Application logs remain local unless an operator exports them. Compose disables
Next/Qdrant telemetry. Setup/scanning downloads dependencies and advisory databases;
configured model calls, OIDC, and remote image ingestion are additional network
flows. This is not an offline-only product or a no-data-leaves-the-machine claim.

The current alpha still requires exact-artifact vulnerability qualification,
broader adversarial model evaluation, clean exported installation/CI checks and
owner approval. Historical assessments expired October 5, 2026. New code, images,
native/embedded dependencies and deployment changes require current evidence.
No zero-vulnerability, production-security, legal-compliance or SLA claim is made.
See [security verification](SECURITY_VERIFICATION.md) and [security policy](../SECURITY.md).
