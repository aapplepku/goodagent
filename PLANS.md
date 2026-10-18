# Execution plan format

For any task expected to touch more than three files, first write or update an execution plan under `plans/`.

Use this template:

```markdown
# <Task name>

## Goal
One precise outcome.

## Context
Relevant docs, files, APIs, and existing behavior.

## Constraints
Architecture, security, compatibility, and scope boundaries.

## Proposed changes
1. ...
2. ...
3. ...

## Data model or API changes
Explicit schemas and migration impact.

## Test plan
Unit, integration, contract, and end-to-end tests.

## Rollback plan
How to revert code and data safely.

## Done when
Observable acceptance criteria.

## Progress
- [ ] Step 1
- [ ] Step 2

## Decisions and deviations
Record discoveries and why the plan changed.
```

Rules:

- Keep plans executable, not aspirational.
- Resolve ambiguity by inspecting the repository and docs before guessing.
- Do not silently expand scope.
- Check off progress as work proceeds.
- Update the plan when implementation reveals a necessary deviation.
- A plan is not complete until tests and documentation are included.
