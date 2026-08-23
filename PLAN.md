# Delivery plan

This plan treats the exercise as one small Agile iteration. Each story has a user-facing outcome, acceptance criteria, and a verification step. Status is updated as work progresses.

## Sprint goal

Deliver a browser-based, read-only HRIS import preview that reports identity and hierarchy problems before any employee data is persisted, and remains linear in the number of source rows.

## Definition of done

- The acceptance criteria in `BASE.md` are demonstrated end to end.
- Parsing and hierarchy analysis are independent of Django's request/response layer.
- The hot path contains no repeated scans for employee or manager lookup.
- Automated tests cover identity rules, manager resolution, cycles, malformed uploads, and a deep hierarchy.
- Setup, test, complexity, assumptions, limitations, and AI usage are documented.
- `python manage.py check` and `python manage.py test` pass.

## Backlog

### Story 1 — Upload a valid HRIS export

As Client Success, I want to upload a CSV in the browser so that I can preview it without writing employee data to a database.

Acceptance criteria:

- [x] GET displays a clear CSV upload form.
- [x] POST accepts UTF-8 with or without a BOM and honors quoted CSV fields.
- [x] Headers may be in any order but must match the documented contract.
- [x] A malformed file produces a useful form error, not a server exception.

### Story 2 — Validate identities

As Client Success, I want every bad source row identified so that I can repair the export.

Acceptance criteria:

- [x] Values are trimmed; email fields are lowercased; employee IDs remain case-sensitive.
- [x] Missing IDs/emails and all occurrences of duplicate IDs/emails are rejected.
- [x] Errors carry the original source row number.
- [x] Identity-invalid rows cannot be managers or hierarchy nodes.

### Story 3 — Preview the reporting hierarchy

As Client Success, I want roots, manager counts, and manager-reference errors so that I can check the org structure.

Acceptance criteria:

- [x] ID-only, email-only, and matching dual manager references resolve correctly regardless of file order.
- [x] Missing, conflicting, and self references produce useful errors.
- [x] Manager-error rows remain accepted, but create neither a relationship nor a root.
- [x] Roots and managers with direct-report counts are displayed.

### Story 4 — Identify reporting cycles

As Client Success, I want exact cycle membership so that I can fix circular reporting relationships.

Acceptance criteria:

- [x] Every employee in a cycle is reported.
- [x] Employees that merely lead into a cycle are not reported as cyclic.
- [x] Detection is iterative, avoiding recursion depth failures on tall hierarchies.

### Story 5 — Make scale and ownership reviewable

As a reviewer, I want tests and concise documentation so that I can verify the design and discuss its trade-offs.

Acceptance criteria:

- [x] Dictionary/counter indexes provide expected O(n) validation and manager resolution.
- [x] Functional-graph traversal provides O(n) cycle analysis; total space is O(n).
- [x] Tests include a deep, non-recursive hierarchy case.
- [x] README includes setup, test, assumptions, limits, time, AI disclosure, and walkthrough notes.

## Implementation sequence

1. [x] Read the brief and inspect repository state.
2. [x] Define domain records, pipeline stages, invariants, and complexity targets.
3. [x] Implement and test the pure analysis core.
4. [x] Connect the core to a minimal Django upload view and template.
5. [x] Run checks/tests and review failure paths.
6. [x] Complete documentation and mark the stories accepted.

## Verification evidence

- `python manage.py check`: no issues.
- `python manage.py test`: 14 tests passed.
- 100,000-row linear-chain sanity check: 100,000 accepted, one root, no issues/cycles, approximately 0.57 seconds on the development machine.
- `git diff --check`: no whitespace errors.

## Technical design

The application is a thin imperative shell around a functional core:

1. `parse_csv` converts the stream into immutable, normalized row values.
2. `validate_identities` counts IDs/emails once and returns accepted rows plus immutable issues.
3. `resolve_hierarchy` builds ID/email dictionaries once, then resolves each accepted row once.
4. `detect_cycle_members` walks the employee-to-manager functional graph iteratively and permanently marks visited nodes.
5. `analyze_csv` composes those stages into one immutable result consumed by the Django view.

Local dictionaries and sets are used inside pure functions for performance. They never escape as mutable result state, so callers observe deterministic inputs-to-outputs behavior without database or global state.
