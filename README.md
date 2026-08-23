# HRIS Import Preview

A small Django application that analyzes an HRIS CSV before any employee or reporting data is written. It shows source and accepted row totals, row-level errors, roots, direct-report counts, and exact reporting-cycle membership. Every result table supports searching, sortable columns, and pagination.

The project deliberately has no models or database configuration. Each upload is parsed for one response and then discarded.

## Setup and run

Python 3.11 or newer is recommended. The project uses the supported [Django 5.2 LTS release line](https://www.djangoproject.com/download/).

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
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
- paginated table wiring, bounded fallback rendering, and safe JSON embedding.

## Design

The Django layer is intentionally thin:

- `imports/views.py` adapts the uploaded binary file into a UTF-8 text stream and renders a result.
- `imports/forms.py` enforces the 50 MB upload limit.
- `imports/analysis.py` contains the framework-independent functional core.
- `imports/static/imports/results-table.js` progressively enhances the result tables without a frontend framework.

The core is a staged pipeline:

1. `parse_csv` uses Python's CSV parser, validates the header, and creates immutable normalized `EmployeeRecord` values.
2. `validate_identities` counts IDs and normalized emails, then rejects every row involved in a duplicate.
3. `resolve_hierarchy` indexes only accepted employees by ID and email before resolving manager references.
4. `detect_cycle_members` iteratively walks the employee-to-manager graph and identifies the looping suffix of each path.
5. `analyze_csv` composes the stages into the immutable `AnalysisResult` consumed by the template.

This is a functional-core/imperative-shell design rather than a claim that all Python code is mutation-free. Pipeline functions are deterministic, do not perform I/O beyond reading their supplied stream, do not touch globals or a database, and return frozen dataclasses/tuples. Local dictionaries, counters, sets, and lists are used inside the functions because they are the practical way to meet the scale target.

## Complexity at approximately 100,000 employees

Let `n` be the number of CSV data rows and `e` the number of valid reporting relationships. Here, `e <= n` because an employee can resolve to at most one manager.

- CSV parsing/normalization: O(n).
- Identity counting and validation: O(n) expected time using two hash-based counters.
- Employee ID/email index creation: O(n) expected time.
- Manager resolution and direct-report counting: O(n) expected time using hash lookups—there are no repeated linear employee scans.
- Cycle detection: O(n + e), which reduces to O(n), because every graph node is permanently visited once.
- Result assembly: O(n), preserving source order instead of sorting.
- Space: O(n) for normalized records, indexes, issues, relationships, and traversal state.

Hash-table operations are described as expected O(1), as is conventional for Python dictionaries and sets. The algorithm is iterative, so a chain near 100,000 employees does not consume the Python call stack.

As a local sanity check on Python 3.13, an in-memory CSV containing a 100,000-person chain completed the core analysis in approximately 0.57 seconds. That number is environment-specific and is not a formal performance guarantee; the data structures and asymptotic behavior are the important review points.

### Result-table complexity

The server serializes result rows once in O(r), where `r` is the number of rows across the four result sections. The browser builds an O(r) lowercase search index once but keeps the rendered DOM bounded to the selected page size (10, 25, 50, or 100 rows per table).

- Initial display and page navigation: O(p), where `p` is the selected page size.
- Search: O(r) for the selected result section, debounced by 150 ms.
- An explicitly requested sort: O(m log m), where `m` is the current number of matching rows. Ties retain source order.
- Changing pages after a search or sort: O(p); the filtered/sorted list is cached until the query or sort changes.

Search and sort are presentation operations after the required O(n) import analysis; they do not add repeated employee lookup scans to validation or hierarchy construction.

In an end-to-end local Django client check, the 100,000-person chain returned HTTP 200 in approximately 0.67 seconds. Its 99,999 manager summaries produced an 11.34 MB response, while only 25 manager rows were present in the fallback DOM. These measurements are environment-specific; the response size is why short-lived server-side result storage is identified below as the next scaling step.

## CSV behavior and assumptions

- The six contract headers are required in any order. Duplicate, missing, or additional headers are treated as a clear file-level error; this intentionally catches the wrong export early.
- UTF-8 files with or without a BOM are supported. Other encodings are rejected with a form error.
- Surrounding whitespace is trimmed from every field. `email` and `manager_email` are lowercased; IDs remain case-sensitive.
- `employee_id` and normalized `email` are required and unique. Every occurrence of a duplicate is rejected, even if one of those rows has another problem.
- An identity-invalid or structurally malformed row cannot be a manager and does not enter hierarchy analysis.
- A manager-error row remains in the accepted count, but creates no reporting edge and is not a root.
- A blank `employee_name` or `department` is allowed because the contract does not require either.
- Empty lines ignored by Python's standard CSV parser are not counted as source rows. For ordinary records, reported source rows match spreadsheet line numbers; a record containing an embedded newline is labeled by the physical line where that CSV record ends.
- Results exist only for the current response. There is no persistence, upload history, authentication, or production deployment configuration.

## Known limitations and next improvements

- The 50 MB cap is a pragmatic guardrail, not a guarantee that all files under it contain no more than 100,000 employees.
- The result is held in memory to render one response. For substantially larger files, stream parsing into compact temporary structures and paginated/spooled results would reduce peak memory.
- The browser still receives every result row as escaped JSON so it can search and sort without persisting the upload. Pagination bounds DOM work, but server-side pagination backed by a short-lived result store would reduce response size for substantially larger files.
- Email values are normalized according to the exercise (trim plus lowercase), not validated for full RFC deliverability.
- CSV formula-like values are displayed as escaped HTML. If results are later exported to a spreadsheet, formula-injection escaping should be added to that export path.

## Agile delivery notes

`PLAN.md` contains the sprint goal, five user stories, acceptance criteria, implementation order, and definition of done used for this implementation. The automated checks are the executable acceptance evidence; a small manual upload remains part of the final walkthrough.

## Approximate time and AI usage

Approximate AI-assisted implementation and verification time: **2.5 hours**, excluding the narrated recording. Replace this with the submitter's actual elapsed time if additional manual work is done.

OpenAI Codex was used to translate the brief into the delivery plan, scaffold the Django project, implement the analysis pipeline and tests, and review complexity/error cases. One accepted suggestion was the iterative path-position cycle algorithm, because it isolates true cycle members without recursion. One changed suggestion was server-side default sorting: source order remains the O(n) default, while optional sorting is isolated in the browser and runs only when requested. No application code or employee data is sent to an external service by the running application.

The submitter remains responsible for reviewing every non-trivial function and narrating their understanding, as required by the exercise.

## Suggested walkthrough outline (under 10 minutes)

1. Upload `examples/sample_hris.csv`; point out the totals, valid roots/manager counts, missing-manager error, two-person cycle, and excluded cycle follower. Demonstrate a search, column sort, page-size change, and page navigation.
2. Trace `upload_preview` into `analyze_csv`, then explain the immutable stage outputs.
3. Show the ID/email counters and indexes and explain why manager rows may appear in any order.
4. Draw one path into a two-person cycle while explaining `position_in_path` and `visited`.
5. Run the tests and connect the duplicate, manager, cycle-tail, malformed-upload, and deep-chain tests to the requirements.
6. Discuss the single-response memory trade-off, HTML result size, and AI choices noted above.
