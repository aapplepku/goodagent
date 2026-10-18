# Security

This is experimental, self-hosted, localhost-only software for non-sensitive test data.
It is not production-ready or suitable for unattended real-money operation.

The frozen v0.1.0-rc1 qualification found no unresolved applicable HIGH or CRITICAL
findings in the shipped simulator runtime within its reviewed local deployment.
Raw dependency/container scanner output, applicability assessments, SBOMs and
residual limitations are retained for reproducibility. This does not mean zero
vulnerabilities or formally verified security. Assessments expired **October 5,
2026**; current development and later releases require refreshed review.
New development is not covered merely because the frozen RC passed.

## Report privately

Do not report suspected vulnerabilities through a public GitHub issue, public
discussion, social media post or public pull request.

Once the repository is public, use GitHub's private **Report a vulnerability**
workflow under **Security / Advisories** whenever available. If that workflow is
unavailable, email **hc414t@gmail.com** with the subject prefix
**[Open Commerce Agent Security]**. Until the repository is public and private
reporting is enabled, use this owner-verified email channel.

Include the affected version or commit, reproduction steps, expected impact,
relevant logs with secrets removed, and any proposed mitigation. Do not include
merchant credentials, API tokens, customer PII, payment information or other
secrets. Use synthetic reproductions. Do not probe systems that you do not own
or have explicit permission to test.

Maintainers will make a reasonable effort to acknowledge and coordinate reports,
but v0.1 does not promise a contractual response or remediation SLA. Security
fixes may be developed privately through GitHub repository security advisories
before coordinated disclosure.

## Supported versions

Only the most recent released minor version is supported during the pre-1.0
period. This policy does not promise production suitability or a stable release.
The current review target is the private self-hosted alpha, separately from the
frozen v0.1.0-rc1 simulator. Its qualification is incomplete. No stable release or
production support is offered. Report the exact commit or tag, since the current
application differs substantially from the frozen RC.

## Future Publication Prerequisites

Only after separate owner authorization to publish, the administrator must:

- Enable GitHub Private Vulnerability Reporting immediately before or immediately
  after making the repository public.
- Confirm administrators are subscribed to repository security-alert notifications.
- Verify the **Report a vulnerability** workflow is visible from a non-admin account.

These are launch-time checks, not completed settings in this local checkout.
The email fallback remains available. See [GitHub's configuration guide](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository).

## Current boundaries

- Compose publishes only loopback ports. Self-hosted setup requires a console-issued
  token and authenticated store membership. The explicit legacy-demo profile retains
  implicit local roles and is not authentication. Never expose it to an untrusted network.
- Browser requests use same-origin proxies, CSP and origin checks. Merchant and
  shopper sessions are separate, with opaque HttpOnly cookies and server-side
  session validation; private preview grants cannot access merchant tools. HTTPS
  deployments require exact configured origins and Secure-cookie/proxy verification.
  Compose uses loopback HTTP and an empty API CORS list. These mechanisms are not a
  production identity or deployment qualification.
- API bodies, headers, queries and expensive/write-like request rates are bounded.
  Endpoint rate limits are per process. Model request/token reservations are shared
  through PostgreSQL across workers and the API; this is not comprehensive distributed
  abuse protection.
- Simulator effects require typed compilation, current policy and preconditions,
  exact-hash approval where required, durable idempotency, audit and reconciliation.
- PostgreSQL queries scope tenant-owned records by tenant ID. This is not a claim
  of production row-level-security isolation or protection from a database owner.
- Audit and budget history have application restrictions and database immutability
  triggers. A privileged database administrator can disable those protections.
- Logs redact tested secret/PII patterns; API errors do not intentionally disclose
  raw exceptions. Redaction is not permission to enter real sensitive data.
- Runtime users are non-root with capabilities dropped and no-new-privileges.
  Application filesystems are read-only. Docker/host compromise is outside the demo boundary.

## Supply chain

Lockfiles pin application dependencies. The release process requires dependency,
secret and image scans plus SBOMs, with exact image identities and findings retained.
`scripts/scan-images.py` scans local built Compose images and writes raw Trivy
reports and CycloneDX SBOMs under `.opencommerce/security-scans/final/`.

A scan completing is not a clean security result. The [detailed evidence](docs/SECURITY_VERIFICATION.md)
distinguishes raw package/advisory records from applicable unresolved findings,
including scope, reachability, exposure, scanner coverage and expiry. Raw records
must not be deleted or severity-adjusted to improve the headline. New, changed,
missing or expired HIGH/CRITICAL assessments fail the gate, as do unresolved
applicable HIGH/CRITICAL findings in shipped runtime. No vendor fix or a working
demo is not a reason to waive those requirements.

See [the threat model](docs/THREAT_MODEL.md) for explicit assumptions and exclusions.
