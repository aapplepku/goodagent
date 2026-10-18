# Security, Privacy, and Multitenancy

## 1. Threat model

Assets:

- commerce platform tokens;
- ad platform tokens;
- merchant financial/unit-cost data;
- product and inventory data;
- order/customer-derived data;
- action permissions;
- budget and pricing controls;
- audit history.

Threats:

- stolen connector credentials;
- cross-tenant data access;
- prompt injection from catalog data;
- forged webhooks;
- replayed approval/action requests;
- duplicate writes;
- malicious or compromised dependencies;
- SSRF through merchant-configured URLs;
- log/trace leakage;
- operator privilege escalation;
- destructive automation after model/provider compromise.

## 2. Security architecture

```text
untrusted browser
  ↓ TLS
web/API authentication
  ↓ tenant + role context
application services
  ↓ typed repositories/providers
encrypted secrets store
  ↓
external commerce/ads APIs

LLM boundary is separate:
sanitized minimum context
  ↓
structured output
  ↓
validation/compiler/policy
  ↓
no direct credentials or writes
```

## 3. Secrets

MVP self-hosted:

- encrypt tokens at application level using an environment-provided master key;
- use authenticated encryption;
- store key version with ciphertext;
- support rotation;
- never expose decrypted token beyond provider client scope;
- redact secret-like fields centrally.

Hosted future:

- cloud KMS/envelope encryption;
- per-environment keys;
- restricted service identity;
- audit decrypt operations.

`.env.example` contains names only. CI uses ephemeral secrets. Documentation tells users not to share tokens in issues.

## 4. Tenant isolation

Every tenant-owned table includes `tenant_id`.

Defense in depth:

1. authenticated request context;
2. repository APIs require tenant scope;
3. composite unique constraints include tenant;
4. foreign keys include tenant where practical;
5. PostgreSQL row-level security planned/enabled for hosted mode;
6. Qdrant filters always include tenant;
7. object-storage prefixes include tenant;
8. queues carry tenant and validate it on load;
9. provider credentials are bound to tenant/integration;
10. tests attempt cross-tenant reads/writes.

Do not trust a `tenant_id` embedded in an LLM output or action payload. Resolve entities under current tenant.

## 5. Authentication and authorization

Use OIDC/JWT for production deployment rather than building password storage.

Requirements:

- issuer/audience/signature validation;
- short-lived access tokens;
- role claims or server-side role mapping;
- CSRF protection where cookies are used;
- secure, HTTP-only, same-site cookies;
- reauthentication or recent-auth requirement for policy broadening, secret changes, and disabling safety controls;
- rate limits on auth and approval endpoints.

Shopify OAuth installation authorizes an integration; it does not automatically grant application user roles.

## 6. Web security

- TLS in non-local deployments;
- strict CORS allowlist;
- CSP;
- clickjacking protection;
- secure cookies;
- input size limits;
- JSON content-type enforcement;
- request timeout;
- rate limiting;
- dependency and container scanning;
- no dynamic template evaluation.

Do not render product HTML directly. Sanitize descriptions and use text or a safe allowlist renderer.

## 7. Webhook security

For each provider:

- verify signature using raw body and timing-safe comparison;
- validate timestamp/replay information where available;
- reject invalid shop/account identifiers;
- size-limit before parsing;
- deduplicate event ID;
- store only minimal receipt;
- return quickly;
- reread authoritative state;
- rate-limit abusive invalid requests without blocking legitimate bursts.

Compliance/data-deletion webhook paths receive the same verification rigor.

## 8. OAuth security

- normalize and validate provider host/domain;
- use cryptographically random state;
- bind state to initiating browser/tenant;
- short expiration;
- one-time use;
- PKCE where supported;
- verify callback signature;
- exact redirect URI;
- do not accept arbitrary post-auth redirects;
- encrypt token immediately;
- separate token metadata from ciphertext;
- revoke/delete on uninstall.

## 9. SSRF and egress

The core product should not fetch arbitrary URLs supplied by merchant/catalog data.

Image URLs remain browser-rendered or processed by a dedicated, restricted image proxy later.

Provider base URLs come from allowlisted adapters. WooCommerce self-hosted domains, when added, require:

- HTTPS by default;
- DNS/IP validation;
- block loopback, link-local, private network, metadata endpoints unless administrator explicitly allows on-prem mode;
- redirect limits;
- re-resolve protection;
- egress timeout.

## 10. LLM security

The LLM gets:

- sanitized summaries;
- opaque evidence IDs;
- allowlisted enums/actions;
- no credentials;
- no raw PII;
- no arbitrary provider response bodies.

Prompts state that catalog/review text is untrusted data, but prompt text is not the security control. The controls are schema validation, entity resolution, compiler logic, policy, capability checks, and action execution isolation.

Model provider requests:

- explicit retention/privacy configuration where available;
- timeout and cost limit;
- content length cap;
- provider allowlist;
- model/version logged;
- safe fallback on outage.

Do not implement model-generated Python/SQL execution.

## 11. Data minimization

MVP needs:

- aggregate order metrics;
- product/variant/catalog;
- inventory;
- discounts;
- pseudonymous session events;
- optional pseudonymous customer reference to distinguish new/returning when authorized.

MVP does not need:

- customer names;
- email;
- phone;
- postal address;
- order notes;
- payment credentials;
- full IP addresses;
- sensitive demographic attributes.

Hashing a direct identifier is still personal data in many contexts. Treat it accordingly and rotate/salt per tenant.

## 12. Data retention

Configurable defaults:

- raw webhook receipt: short retention;
- normalized order facts: necessary analysis window;
- behavioral events: configurable, pseudonymous;
- LLM request metadata: minimal;
- prompts/responses: off by default or short retention with redaction;
- audit records: longer retention, no secrets/PII;
- deleted integration secrets: immediate cryptographic deletion.

Provide:

- tenant export;
- tenant deletion;
- customer-data deletion handler when required;
- integration uninstall cleanup;
- documented backup retention.

## 13. Privacy and consent

Web Pixel/storefront event collection must respect platform consent state and merchant configuration.

UI must disclose:

- events collected;
- purposes;
- retention;
- model providers receiving sanitized data;
- autonomy and action logs;
- how to disable/delete.

Do not enable personalized ranking without a consent-compatible identity/event design.

## 14. Supply-chain security

CI:

- lock dependencies;
- dependency vulnerability scan;
- secret scan;
- static analysis;
- container scan;
- SBOM generation;
- signed release artifacts when project matures;
- minimal non-root containers;
- read-only filesystem where practical.

Pin GitHub Actions by commit SHA for high-assurance workflows.

Review all agent/plugin contributions because connector code receives powerful credentials.

## 15. Plugin/connector trust

MVP connectors are in-tree and reviewed.

Future plugin system needs:

- signed/verified packages;
- declared capabilities;
- least-privilege credentials;
- process/container isolation;
- explicit egress;
- resource limits;
- version compatibility;
- audit attribution;
- merchant confirmation before activation.

Do not dynamically install arbitrary code from an agent request.

## 16. Database security

- separate application and migration roles;
- least privilege;
- encrypted connections;
- backups;
- point-in-time recovery for hosted mode;
- parameterized queries;
- no raw SQL generated from user input;
- append-only audit permissions;
- row-level security in hosted deployment;
- migration review.

Sensitive columns can use application-layer encryption.

## 17. Queue and worker security

- jobs contain IDs, not secrets or large payloads;
- worker reloads authoritative records;
- signed/authenticated Redis connection;
- separate queues for reads and writes;
- write worker has narrower deployment permissions;
- maximum retries;
- dead-letter queue;
- no serialized Python objects/pickle from untrusted sources.

## 18. Action security

External write worker:

- checks kill switch;
- verifies tenant/integration binding;
- reloads policy;
- verifies action hash/approval;
- checks preconditions;
- reserves budget;
- obtains entity lock;
- calls only typed provider method;
- stores safe response;
- reconciles.

The planner service should not possess direct write credentials in a hardened hosted deployment. A dedicated executor service can hold them.

## 19. Security tests

- forged Shopify webhook;
- replayed webhook;
- invalid OAuth state;
- malicious shop domain;
- token log-redaction;
- cross-tenant database access;
- cross-tenant Qdrant query;
- approval replay after action mutation;
- role escalation;
- prompt injection in product text;
- malicious HTML in catalog;
- SSRF URL when WooCommerce connector is introduced;
- duplicate idempotency key;
- queue payload tampering;
- kill switch race;
- secret deletion after uninstall;
- PII absent from LLM fixture.

## 20. Incident response

Runbooks:

1. leaked provider token;
2. unauthorized price/discount change;
3. budget overspend;
4. cross-tenant data exposure;
5. compromised dependency;
6. model provider outage;
7. data deletion failure.

Immediate controls:

- deployment/tenant/integration kill switches;
- revoke connector;
- stop workers;
- preserve audit evidence;
- reconcile remote state;
- rollback safe actions;
- notify affected operators;
- rotate keys.

## 21. Definition of done

Before public write beta:

- threat model reviewed;
- secret encryption and rotation path tested;
- tenant isolation tests pass;
- webhook/OAuth verification tests pass;
- LLM receives no prohibited data in fixtures;
- kill switch race tests pass;
- dependency/secret/container scans run in CI;
- deletion/uninstall workflow tested;
- incident and rollback runbooks exist.
