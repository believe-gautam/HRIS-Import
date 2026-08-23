# HRIS Import Preview

A small Django application that analyzes an HRIS CSV before any employee or reporting data is written. It shows source and accepted row totals, row-level errors, roots, direct-report counts, and exact reporting-cycle membership. Every result table supports searching, sortable columns, and pagination.

The full CSV is analyzed before any database write. After a successful analysis, the summary and displayed issue/root/manager/cycle details are saved to local SQLite history. The raw uploaded CSV is never stored.

## Setup and run

Python 3.11 or newer is recommended. The project uses the supported [Django 5.2 LTS release line](https://www.djangoproject.com/download/).

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. A demonstration file is available at `examples/sample_hris.csv`.

## Run the tests

```bash
python manage.py check
python manage.py test
```

If Node.js is available, the dependency-free browser script can also be syntax-checked with:

```bash
node --check imports/static/imports/results-table.js
```

The test suite covers:

- trimming, case normalization, headers in any order, quoted commas, and UTF-8 BOMs;
- required and duplicate identities, including exclusion from manager lookup;
- ID-only, email-only, and dual manager references;
- missing, conflicting, and self-manager errors;
- exact cycle membership (excluding a tail that leads into a cycle);
- a 20,000-employee-deep hierarchy, demonstrating iterative rather than recursive traversal;
- malformed headers, CSV syntax, and invalid UTF-8 at both the core and browser boundaries;
- paginated table wiring, bounded fallback rendering, and safe JSON embedding;
- atomic SQLite save/load round trips, filename sanitization, and history list/detail pages.

## Design

The Django layer is intentionally thin:

- `imports/views.py` adapts the uploaded binary file into a UTF-8 text stream and renders a result.
- `imports/forms.py` enforces the 50 MB upload limit.
- `imports/analysis.py` contains the framework-independent functional core.
- `imports/persistence.py` atomically stores completed analyses using bounded batched writes.
- `imports/models.py` defines scan summaries, row issues, and categorized employee details.
- `imports/tables.py` applies an allowlisted database search/sort and returns one bounded result page.
- `imports/static/imports/results-table.js` progressively enhances the result tables without a frontend framework.

The core is a staged pipeline:

1. `parse_csv` uses Python's CSV parser, validates the header, and creates immutable normalized `EmployeeRecord` values.
2. `validate_identities` counts IDs and normalized emails, then rejects every row involved in a duplicate.
3. `resolve_hierarchy` indexes only accepted employees by ID and email before resolving manager references.
4. `detect_cycle_members` iteratively walks the employee-to-manager graph and identifies the looping suffix of each path.
5. `analyze_csv` composes the stages into the immutable `AnalysisResult` consumed by the template.

Only after stage 5 succeeds does `save_analysis_result` open a transaction and persist history. It writes one `ImportScan` summary plus `ScanIssue` and `ScanEmployeeDetail` rows in fixed-size batches. The upload then redirects to the saved scan. Detail views query at most one result page per category instead of reconstructing or serializing the full analysis.

This is a functional-core/imperative-shell design rather than a claim that all Python code is mutation-free. Analysis functions are deterministic, do not touch globals or a database, and return frozen dataclasses/tuples. Local dictionaries, counters, sets, and lists are used inside those functions because they are the practical way to meet the scale target. Django views and `persistence.py` form the explicit side-effecting shell.

## Complexity at approximately 100,000 employees

Let `n` be the number of CSV data rows and `e` the number of valid reporting relationships. Here, `e <= n` because an employee can resolve to at most one manager.

- CSV parsing/normalization: O(n).
- Identity counting and validation: O(n) expected time using two hash-based counters.
- Employee ID/email index creation: O(n) expected time.
- Manager resolution and direct-report counting: O(n) expected time using hash lookups—there are no repeated linear employee scans.
- Cycle detection: O(n + e), which reduces to O(n), because every graph node is permanently visited once.
- Result assembly: O(n), preserving source order instead of sorting.
- SQLite history writing: O(r) batched inserts after analysis succeeds, where `r` is the number of saved result-detail rows.
- Space: O(n) for normalized records, indexes, issues, relationships, and traversal state.

Hash-table operations are described as expected O(1), as is conventional for Python dictionaries and sets. The algorithm is iterative, so a chain near 100,000 employees does not consume the Python call stack.

As a local sanity check on Python 3.13, an in-memory CSV containing a 100,000-person chain completed the core analysis in approximately 0.57 seconds. That number is environment-specific and is not a formal performance guarantee; the data structures and asymptotic behavior are the important review points.

The same 100,000-person result persisted 100,000 root/manager detail rows to an isolated SQLite test database in approximately 3.03 seconds using bounded batches and query-supporting indexes. This is environment-specific, but confirms that the history path does not build a second 100,000-item insert list or issue one ORM insert call per employee.

### Result-table complexity

Result tables use true server-side pagination. The detail page embeds only the first 25 rows of each category, and every search, sort, or page action calls a read-only JSON endpoint that returns at most the selected page size (10, 25, 50, or 100).

Each table provides First/Previous/Next/Last actions, nearby numbered pages with compact ellipses, and a validated **Go to page** field. Enter submits the requested page, and navigation returns the viewport to the relevant table while honoring the browser's reduced-motion preference.

Scan History uses the same direct-page controls and keeps the active filename/ID search and sort choice when moving between pages.

- Browser memory and DOM work: O(p), where `p <= 100`, independent of total saved result rows.
- Database page response memory: O(p).
- Indexed category filtering and supported column ordering are handled by SQLite; free-text `contains` searches can still scan O(r) rows in that category but do not materialize them in the web process.
- Offset pagination can become slower on very late pages, but its response remains bounded. Cursor pagination would be the next improvement for multi-million-row history tables.

In a 100,000-person history check, the saved-scan HTML was approximately 22.4 KB and a late manager-page JSON response was approximately 2.9 KB for 24 rows out of 99,999 managers. The previous front-end implementation produced an approximately 11.34 MB page for that case.

## CSV behavior and assumptions

- The six contract headers are required in any order. Duplicate, missing, or additional headers are treated as a clear file-level error; this intentionally catches the wrong export early.
- UTF-8 files with or without a BOM are supported. Other encodings are rejected with a form error.
- Surrounding whitespace is trimmed from every field. `email` and `manager_email` are lowercased; IDs remain case-sensitive.
- `employee_id` and normalized `email` are required and unique. Every occurrence of a duplicate is rejected, even if one of those rows has another problem.
- An identity-invalid or structurally malformed row cannot be a manager and does not enter hierarchy analysis.
- A manager-error row remains in the accepted count, but creates no reporting edge and is not a root.
- A blank `employee_name` or `department` is allowed because the contract does not require either.
- Empty lines ignored by Python's standard CSV parser are not counted as source rows. For ordinary records, reported source rows match spreadsheet line numbers; a record containing an embedded newline is labeled by the physical line where that CSV record ends.
- Imports above 250,000 data rows stop early with a clear validation error. This bounds memory for a project designed around roughly 100,000 employees; safely processing millions would require a disk-backed or external-sort pipeline rather than this in-memory analyzer.
- Successful analysis summaries and displayed detail categories are retained in SQLite until the database is removed or a future retention feature deletes them. Malformed uploads do not create history records.
- The raw CSV contents are not saved, so a history entry can reproduce the analysis preview but cannot reproduce or download the original export.

## Known limitations and next improvements

- The 50 MB cap is a pragmatic guardrail, not a guarantee that all files under it contain no more than 100,000 employees.
- The result is held in memory to render one response. For substantially larger files, stream parsing into compact temporary structures and paginated/spooled results would reduce peak memory.
- Free-text contains searches over very large categories are database scans. SQLite FTS or PostgreSQL trigram/full-text indexes would improve that workload.
- Very late pages use SQL offsets. Keyset/cursor pagination would provide more consistent latency at multi-million-row scale.
- SQLite is appropriate for this single-machine exercise, but write-heavy multi-user deployment would call for PostgreSQL and background import jobs.
- There is not yet a retention policy or delete-history action. This is intentional because deletion behavior and authorization need an explicit product decision.
- Email values are normalized according to the exercise (trim plus lowercase), not validated for full RFC deliverability.
- CSV formula-like values are displayed as escaped HTML. If results are later exported to a spreadsheet, formula-injection escaping should be added to that export path.

## Agile delivery notes

`PLAN.md` contains the sprint goal, seven user stories, acceptance criteria, implementation order, and definition of done used for this implementation. The automated checks are the executable acceptance evidence; a small manual upload remains part of the final walkthrough.

## Approximate time and AI usage

Approximate AI-assisted implementation and verification time: **5 hours**, excluding the narrated recording. Replace this with the submitter's actual elapsed time if additional manual work is done.

OpenAI Codex was used to translate the brief into the delivery plan, scaffold the Django project, implement the analysis pipeline, SQLite history, and tests, and review complexity/error cases. One accepted suggestion was isolating database writes in a transactional persistence adapter so the analysis core remains pure. One changed suggestion was storing the whole result as one JSON blob: normalized detail rows were used instead so history summaries stay cheap to query and the saved categories remain explicit. No application code or employee data is sent to an external service by the running application.

The submitter remains responsible for reviewing every non-trivial function and narrating their understanding, as required by the exercise.

## Suggested walkthrough outline (under 10 minutes)

1. Upload `examples/sample_hris.csv`; point out the totals, valid roots/manager counts, missing-manager error, two-person cycle, and excluded cycle follower. Demonstrate search/sort, a numbered page, direct page jump, and show in browser developer tools that only one result page is fetched.
2. Trace `upload_preview` into `analyze_csv`, explain the immutable stage outputs, and show that persistence happens only after analysis succeeds.
3. Show the ID/email counters and indexes and explain why manager rows may appear in any order.
4. Draw one path into a two-person cycle while explaining `position_in_path` and `visited`.
5. Run the tests and connect the duplicate, manager, cycle-tail, malformed-upload, and deep-chain tests to the requirements.
6. Discuss SQLite/batched-write and client-side-result-size trade-offs, plus the AI choices noted above.
