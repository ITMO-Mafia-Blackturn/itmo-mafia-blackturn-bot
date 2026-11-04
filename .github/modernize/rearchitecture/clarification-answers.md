---
schema: clarification-answers/v1
status: submitted
generated_at: "2026-11-04T20:52:44.354Z"
scope: [backend, generic]
questions_file: clarification-questions.json
---

# Rearchitecture Clarification Answers

## ⚙️ Backend

- **B1** Which Python Telegram-bot framework and Python runtime version should remain the target? The supplied facts identify a Python Telegram bot but do not name exact framework/runtime versions. You may confirm that the implementation should retain the versions already in the project.
  - answer: Keep the existing Python Telegram-bot framework and Python runtime versions; identify exact versions from the project
  - source: user
- **B2** What compatibility policy should apply to existing externally visible bot/API behavior while editing and refactoring?
  - answer: must preserve
  - source: user
- **B3** Should this work keep the existing schema and migration history, adding a new migration only if required, or use another data-migration approach? The prior Tournament name/description migration must remain intact.
  - answer: in-place
  - source: user
- **B4** Which authentication/authorization mechanism should the admin-only edit flow use?
  - answer: Preserve existing admin authorization mechanism and patterns
  - source: user
- **B5** Are there latency, throughput, availability, or other service-level targets beyond matching the current production baseline?
  - answer: Match current production baseline; no regression
  - source: user

## 📋 General

- **G1** What outcome defines success for this work?
  - answer: Preserve existing behavior and working-tree changes; complete the tournament editing and large-module refactor; validate imports, syntax, and available tests; report modules split, feature details, operational steps, and exact validation performed. Code is more readable and supportable
  - source: user
- **G2** Which areas must remain untouched?
  - answer: Do not revert or alter unrelated in-progress changes, including the Dockerfile change; do not refactor small files, dependencies, venv, logs, or migrations; avoid unrelated cleanup/formatting; do not commit.
  - source: user
- **G3** How should existing tests be treated during implementation and validation?
  - answer: must pass
  - source: user
- **G5** Are there additional requirements, exclusions, dependencies, compliance rules, or operational constraints not covered above?
  - answer: None beyond the decisions listed in this specification.
  - source: user
