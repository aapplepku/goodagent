## Change

Describe the behavior, scope and relevant execution plan. Separate implemented
behavior from future design notes.

## Evidence

- [ ] Focused tests cover the change and relevant failure paths.
- [ ] Lint, formatting, types, units/contracts and integration checks pass.
- [ ] UI changes pass production Compose E2E and desktop/mobile inspection.
- [ ] Generated OpenAPI/client artifacts are current.
- [ ] Benchmark changes retain inputs, unfavorable rows and version provenance.

## Safety and operations

- [ ] Tenant predicates and domain/provider boundaries are preserved.
- [ ] Consequential effects remain inside the executor with policy, approval,
      idempotency, preconditions, audit and rollback metadata.
- [ ] No live provider, secret, customer PII or inventory-quantity write was introduced.
- [ ] Migrations, configuration changes, rollback steps and limitations are documented.
- [ ] Review findings are listed with severity; no unresolved BLOCKER/HIGH is concealed.
- [ ] No package, image, tag, release or repository was published without owner approval.

- [ ] Every contributed commit has the author's DCO 1.1 sign-off and matching
      sign-offs from any coauthors; no one signed on another person's behalf.

List commands actually run and any unexecuted gates. Contributions use Apache-2.0;
contributors retain their own copyright. See CONTRIBUTING.md and DCO.md.
