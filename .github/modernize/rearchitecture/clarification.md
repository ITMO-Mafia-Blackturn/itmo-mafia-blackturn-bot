---
schema: clarification/v1
generated_at: "2026-11-04T20:49:37Z"
scope:
  - backend
  - generic
clarity_score: 0.17
rounds: 1
gaps:
  - backend.api.contract_preservation
  - backend.data.migration_strategy
  - backend.auth.framework
  - backend.nfr.sla
  - generic.out_of_scope
blocking_gaps:
  - backend.target.framework
---

# Scenario Clarification

## Backend

- **Target framework**: Keep the existing Python Telegram bot stack in place. The precise framework/library version is not established by the available project profile and must be identified during implementation planning; no stack upgrade is requested.
- **API contract preservation**: Must preserve existing bot behavior and interfaces except for the additive admin-only tournament edit flow. (Default assumption; confirm against the existing behavior during implementation.)
- **Data migration strategy**: TBD / assess in research phase. Persist edits transactionally; determine whether the existing schema supports all editable fields before deciding if a migration is needed. (Default)
- **Auth framework**: Preserve the existing authorization mechanism; restrict the new edit flow to admins. (Default for framework; admin-only access is user-specified.)
- **SLA targets**: Match the current production baseline; no new SLA target specified. (Default)

## Generic

- **Success definition**: Preserve existing working-tree changes; provide an admin-only tournament edit flow with validation and transactional persistence; split all large source modules in `code/` into cohesive smaller files; perform focused validation; do not create a commit. Editable tournament fields are name, description, place, date, registration deadline, total capacity, and guest capacity. Reject any capacity reduction below the number of existing active registrations and explain the rejection.
- **Out of scope**: No unrelated feature changes are requested. (Default boundary; scope is limited to the requested tournament-edit flow and source-module decomposition.)
- **Existing test posture**: Partial — perform focused validation of the tournament edit flow and affected modules; no comprehensive test-suite policy was specified.
- **Output location**: Not applicable; this is an in-place enhancement.
- **Additional constraints**: Scope module decomposition to all large source files in `code/`. Preserve pre-existing working-tree changes. Keep edit access admin-only. Validate editable values and persist changes transactionally. Capacity reductions below existing active registrations must be rejected with an explanatory message. Run focused validation and do not commit.

## Gaps & Defaults Applied

- `backend.api.contract_preservation` — resolution: default; default used: `must preserve`; assumption: existing bot behavior and interfaces remain stable except for the additive edit flow.
- `backend.data.migration_strategy` — resolution: default; default used: `TBD / assess in research phase`; determine schema/migration needs without presuming a schema change.
- `backend.auth.framework` — resolution: default; default used: preserve the existing authorization mechanism.
- `backend.nfr.sla` — resolution: default; default used: match the current production baseline.
- `generic.out_of_scope` — resolution: default; default used: no explicit exclusions beyond the requested work.

### Blocking Gaps

- `backend.target.framework` — the project profile identifies a Python Telegram bot and an unchanged stack, but does not identify the exact framework/library version. Record the current version during planning; no target-version change is requested.

## Downstream Usage Notes

- The user-specified scope, fields, access policy, persistence requirement, capacity-reduction rule, validation expectation, and no-commit constraint are resolved and must not be re-asked.
- Treat the backend defaults as assumptions. The exact existing framework version is a planning-time fact to discover, not a request to upgrade it.
- The clarification pass is complete per the user's instruction to proceed without another form; the framework-version gap is carried forward for planning.

## Upstream Artifacts Consumed

- `.github/modernize/rearchitecture/artifacts/project-profile.yaml` — used for the in-place Python Telegram bot stack and unchanged-runtime context.

## Evidence Mapping

- `project-profile.yaml#assessment.change_type/rationale` → unchanged-stack, in-place scope in **Backend / Target framework**.
- `project-profile.yaml#project.languages/structure/notes` → Python Telegram bot context and preservation of in-progress work in **Backend** and **Generic / Success definition**.
- User-supplied clarification in this turn → exact editable fields, admin-only access, transactional persistence, active-registration capacity rejection, focused validation, no commit, and `code/` module scope in **Generic / Success definition** and **Additional constraints**.
