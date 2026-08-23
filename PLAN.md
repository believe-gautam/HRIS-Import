# Delivery plan

This plan treats the exercise as one small Agile iteration. Each story has a user-facing outcome, acceptance criteria, and a verification step. Status is updated as work progresses.

## Sprint goal

Deliver a browser-based HRIS import preview that completes identity and hierarchy analysis before persisting its results, keeps the raw file out of storage, and remains linear in the number of source rows.

## Definition of done

- The acceptance criteria in `BASE.md` are demonstrated end to end.
- Parsing and hierarchy analysis are independent of Django's request/response layer.
- The hot path contains no repeated scans for employee or manager lookup.
- Automated tests cover identity rules, manager resolution, cycles, malformed uploads, and a deep hierarchy.
- Setup, test, complexity, assumptions, limitations, and AI usage are documented.
- `python manage.py check` and `python manage.py test` pass.

## Backlog

### Story 1 — Upload a valid HRIS export

As Client Success, I want to upload a CSV in the browser so that I can preview it before any result details are written to the database.

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

### Story 6 — Navigate large result sets

As Client Success, I want to search, sort, and page through each result section so that I can inspect a large export without an unmanageably large table.

Acceptance criteria:

- [x] Each result section has server-side case-insensitive search across its visible fields.
- [x] Every column can be sorted ascending or descending with an accessible state indicator.
- [x] Page size can be set to 10, 25, 50, or 100, with previous/next navigation and result counts.
- [x] First/Last, nearby numbered pages, and a validated Enter-enabled page jump support direct navigation.
- [x] Only the active page is queried and rendered; the server returns at most 100 rows per request.
- [x] Initial result JSON is safely escaped and bounded to 25 rows per category, which also serves as the JavaScript-free fallback.

### Story 7 — Revisit previous scans

As Client Success, I want successful analysis details saved in SQLite and available from a history page so that I can revisit earlier scans without retaining the source file.

Acceptance criteria:

- [x] Persistence runs only after the complete analysis succeeds and is atomic.
- [x] Scan summaries, issues, roots, managers, and cycle members are saved with batched inserts; raw CSV bytes are not stored.
- [x] History is searchable, sortable, and server-paginated at 20 scans per page.
- [x] A saved scan reopens the shared searchable/sortable/paginated result view.
- [x] Malformed uploads create no history row, and filenames are reduced to safe basenames.

### Story 8 — Bound oversized workloads

As an operator, I want a large upload or result set to fail clearly or remain page-bounded so that it cannot exhaust the browser or application process.

Acceptance criteria:

- [x] Successful uploads redirect to saved results and never serialize the complete result into one response.
- [x] Result searches, sorts, and pages are allowlisted database queries with page sizes capped at 100.
- [x] SQLite persistence consumes fixed-size insert batches rather than constructing a second full-size detail list.
- [x] CSV ingestion stops above 250,000 rows with a clear error instead of attempting unbounded in-memory analysis.
- [x] A 100,000-row scale check produces a roughly 22.4 KB detail page and a roughly 2.9 KB late-page response.

## Implementation sequence

1. [x] Read the brief and inspect repository state.
2. [x] Define domain records, pipeline stages, invariants, and complexity targets.
3. [x] Implement and test the pure analysis core.
4. [x] Connect the core to a minimal Django upload view and template.
5. [x] Run checks/tests and review failure paths.
6. [x] Complete documentation and mark the stories accepted.
7. [x] Add searchable, sortable, paginated result tables and scale-review their behavior.
8. [x] Add atomic SQLite scan history with list and detail pages.
9. [x] Replace front-end pagination with bounded server-side result queries and add ingestion guardrails.

## Verification evidence

- `python manage.py check`: no issues.
- `python manage.py test`: 22 tests passed.
- `node --check imports/static/imports/results-table.js`: passed.
- 100,000-row linear-chain sanity check: 100,000 accepted, one root, no issues/cycles, approximately 0.57 seconds on the development machine.
- 100,000-row SQLite history check: 100,000 categorized detail rows saved in bounded batches in approximately 3.03 seconds; saved-scan HTML was 22.4 KB and a late 24-row API page was 2.9 KB.

## Technical design

The application is a thin imperative shell around a functional core:

1. `parse_csv` converts the stream into immutable, normalized row values.
2. `validate_identities` counts IDs/emails once and returns accepted rows plus immutable issues.
3. `resolve_hierarchy` builds ID/email dictionaries once, then resolves each accepted row once.
4. `detect_cycle_members` walks the employee-to-manager functional graph iteratively and permanently marks visited nodes.
5. `analyze_csv` composes those stages into one immutable result consumed by the Django view.
6. `save_analysis_result` persists that completed result atomically with batched SQLite writes.
7. `get_table_page` applies allowlisted search/sort parameters and returns a bounded database page to the shared result view.

Local dictionaries and sets are used inside pure functions for performance. They never escape as mutable result state, so callers observe deterministic inputs-to-outputs behavior. Database side effects are isolated in `imports/persistence.py` and occur only after analysis.
