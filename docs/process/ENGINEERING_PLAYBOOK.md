# Engineering Playbook

This repository follows a design-first, test-first workflow.

## Delivery Workflow

1. Define the problem and success criteria.
2. Write a technical design document before coding.
3. Run design review and resolve blocking feedback.
4. Create an implementation plan split into small increments.
5. Write tests first for each increment (or update tests before implementation when true TDD is not possible).
6. Implement in small PRs with strict scope.
7. Run code review with at least two approvals for high-risk changes.
8. Validate in staging before production rollout.

## Required Artifacts Per Feature

- `docs/design/<feature-name>.md`
- `docs/plans/<feature-name>.md`
- `docs/tests/<feature-name>.md`
- Linked PRs for each increment

## Definition of Ready (DoR)

- Problem statement is explicit.
- Scope and non-goals are explicit.
- API contracts are defined (request, response, errors).
- Data model changes are listed.
- Risk and rollback strategy are defined.
- Test strategy is defined.

## Definition of Done (DoD)

- All planned tests pass.
- CI passes for backend and frontend.
- ESL-sensitive behavior has explicit test coverage.
- Monitoring/logging impact documented.
- Staging validation completed and documented.
- Rollback steps verified.

## Branch and PR Strategy

- Use short-lived branches.
- Keep PRs small and single-purpose.
- Prefer incremental merges over long-running feature branches.
- If a change is risky, gate it behind a feature flag.

## Testing Policy

- Unit tests for core logic.
- Integration tests for route and service boundaries.
- Contract tests for frontend/backend API compatibility.
- Regression tests for every production bug.

## Review Policy

- Every PR includes:
  - What changed
  - Why it changed
  - Risks
  - Test evidence
- High-risk code paths require two reviewers.
- Reviewers block merge on correctness gaps, not style nits.

## Release Policy

- No direct production deploy without staging verification.
- Document migration and rollback steps in the PR.
- Post-deploy checks are mandatory for critical paths.
