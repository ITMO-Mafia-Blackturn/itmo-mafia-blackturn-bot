## User Input

> Implement the user's request in this repository end-to-end. User clarified: refactor all large source files in code/ into cohesive responsibility-based modules; add admin ability to edit all tournament fields (name, description, place, date, registration deadline, total capacity, guest capacity); reject saving a total/guest capacity reduction below the number of existing active registrations and explain the minimum. Preserve existing behavior and existing in-progress working-tree changes; do not revert unrelated Dockerfile change. Previous task introduced Tournament.name and Tournament.description plus migration_tournament_name_description.sql, creation form, docs. Integrate with that current state; preserve it. Refactor large application modules (not dependencies, venv, logs, migrations) along cohesive functionality boundaries; make small, behavior-preserving modules, adjust imports/router inclusion accordingly. Scope is all large Python source files in code/, not a rewrite of every small file. Add/adjust focused tests if existing test infrastructure permits; validate imports/syntax and tests. The editing flow should be admin-only, consistent with current bot UI/FSM patterns, validate all fields, and persist transactionally using repository/service layer. Think through date/deadline and guest constraints; maintain capacity invariants. Update README and migration guidance only if required. Do not commit. Report modules split, feature details, migration/operational steps if any. Bounded stop: finish the feature, structural decomposition of large code/ sources, focused validation; avoid unrelated cleanup or formatting. User subsequently clarified inline: proceed now; do not open another clarification form.

**Project started**: 2026-11-04T20:46:47Z

## Tasks

### Phase: Analysis
- ⏳ t1 [architect] Analyze application boundaries and migration constraints

### Phase: Implementation
- ⏳ t2 [backend] Implement tournament editing and decompose large application modules [deps: t1]

### Phase: Review
- ⏳ t3 [security] Audit admin-only editing and validation boundaries [deps: t2]

### Phase: Validation
- ⏳ t4 [tester] Validate imports, syntax, focused behavior, and regressions [deps: t3]
