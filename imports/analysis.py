"""Pure HRIS CSV parsing, validation, and hierarchy analysis.

The public functions in this module do not depend on Django. Each pipeline stage
accepts ordinary values and returns immutable dataclasses, which keeps the rules
easy to test while still allowing efficient local dictionaries and sets.
"""

from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TextIO


CSV_HEADERS = (
    "employee_id",
    "employee_name",
    "email",
    "manager_id",
    "manager_email",
    "department",
)


class CSVImportError(ValueError):
    """A file-level error that prevents row analysis."""


@dataclass(frozen=True, slots=True)
class EmployeeRecord:
    source_row: int
    employee_id: str
    employee_name: str
    email: str
    manager_id: str
    manager_email: str
    department: str
    format_errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EmployeeSummary:
    employee_id: str
    employee_name: str
    email: str
    department: str


@dataclass(frozen=True, slots=True)
class RowIssue:
    source_row: int
    messages: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ParsedCSV:
    rows: tuple[EmployeeRecord, ...]

    @property
    def total_rows(self) -> int:
        return len(self.rows)


@dataclass(frozen=True, slots=True)
class IdentityValidation:
    accepted: tuple[EmployeeRecord, ...]
    issues: tuple[RowIssue, ...]


@dataclass(frozen=True, slots=True)
class ManagerSummary:
    employee: EmployeeSummary
    direct_report_count: int


@dataclass(frozen=True, slots=True)
class HierarchyAnalysis:
    roots: tuple[EmployeeSummary, ...]
    managers: tuple[ManagerSummary, ...]
    cyclic_employees: tuple[EmployeeSummary, ...]
    issues: tuple[RowIssue, ...]


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    total_rows: int
    accepted_count: int
    issues: tuple[RowIssue, ...]
    roots: tuple[EmployeeSummary, ...]
    managers: tuple[ManagerSummary, ...]
    cyclic_employees: tuple[EmployeeSummary, ...]


def _normalized(value: str | None, *, lowercase: bool = False) -> str:
    cleaned = (value or "").strip()
    return cleaned.lower() if lowercase else cleaned


def _validate_headers(fieldnames: list[str] | None) -> None:
    if not fieldnames:
        raise CSVImportError("The CSV is empty or has no header row.")

    duplicates = sorted(
        header for header, count in Counter(fieldnames).items() if count > 1
    )
    missing = sorted(set(CSV_HEADERS) - set(fieldnames))
    unexpected = sorted(set(fieldnames) - set(CSV_HEADERS))

    problems: list[str] = []
    if duplicates:
        problems.append(f"duplicate headers: {', '.join(duplicates)}")
    if missing:
        problems.append(f"missing headers: {', '.join(missing)}")
    if unexpected:
        problems.append(f"unexpected headers: {', '.join(unexpected)}")

    if problems:
        raise CSVImportError("Invalid CSV header (" + "; ".join(problems) + ").")


def parse_csv(stream: TextIO) -> ParsedCSV:
    """Parse and normalize a CSV stream in one pass.

    File-level syntax/header failures raise ``CSVImportError``. A row with the
    wrong column count is retained with a format error so its source row can be
    reported alongside other row-level validation failures.
    """

    try:
        reader = csv.DictReader(stream, strict=True)
        _validate_headers(reader.fieldnames)

        records: list[EmployeeRecord] = []
        for raw_row in reader:
            format_errors: list[str] = []
            if None in raw_row:
                format_errors.append("Row has more columns than the CSV header.")
            if any(raw_row.get(header) is None for header in CSV_HEADERS):
                format_errors.append("Row has fewer columns than the CSV header.")

            records.append(
                EmployeeRecord(
                    source_row=reader.line_num,
                    employee_id=_normalized(raw_row.get("employee_id")),
                    employee_name=_normalized(raw_row.get("employee_name")),
                    email=_normalized(raw_row.get("email"), lowercase=True),
                    manager_id=_normalized(raw_row.get("manager_id")),
                    manager_email=_normalized(
                        raw_row.get("manager_email"), lowercase=True
                    ),
                    department=_normalized(raw_row.get("department")),
                    format_errors=tuple(format_errors),
                )
            )
    except UnicodeDecodeError as exc:
        raise CSVImportError("The file must be valid UTF-8 text.") from exc
    except csv.Error as exc:
        raise CSVImportError(f"Malformed CSV near line {reader.line_num}: {exc}.") from exc

    return ParsedCSV(rows=tuple(records))


def validate_identities(rows: tuple[EmployeeRecord, ...]) -> IdentityValidation:
    """Validate required/unique identities with two counters and one row pass."""

    id_counts = Counter(row.employee_id for row in rows if row.employee_id)
    email_counts = Counter(row.email for row in rows if row.email)

    accepted: list[EmployeeRecord] = []
    issues: list[RowIssue] = []

    for row in rows:
        messages = list(row.format_errors)

        if not row.employee_id:
            messages.append("Employee ID is required.")
        elif id_counts[row.employee_id] > 1:
            messages.append(
                f"Employee ID '{row.employee_id}' appears more than once."
            )

        if not row.email:
            messages.append("Email is required.")
        elif email_counts[row.email] > 1:
            messages.append(f"Email '{row.email}' appears more than once.")

        if messages:
            issues.append(RowIssue(row.source_row, tuple(messages)))
        else:
            accepted.append(row)

    return IdentityValidation(accepted=tuple(accepted), issues=tuple(issues))


def detect_cycle_members(manager_by_employee: Mapping[str, str]) -> frozenset[str]:
    """Return exact cycle members from an employee->manager functional graph.

    Each node is permanently visited once. The per-walk position dictionary lets
    us slice only the cycle when a path loops, excluding employees that feed into
    that cycle. The iterative walk also supports chains deeper than Python's
    recursion limit.
    """

    visited: set[str] = set()
    cycle_members: set[str] = set()

    for start in manager_by_employee:
        if start in visited:
            continue

        path: list[str] = []
        position_in_path: dict[str, int] = {}
        current = start

        while (
            current in manager_by_employee
            and current not in visited
            and current not in position_in_path
        ):
            position_in_path[current] = len(path)
            path.append(current)
            current = manager_by_employee[current]

        if current in position_in_path:
            cycle_members.update(path[position_in_path[current] :])

        visited.update(path)

    return frozenset(cycle_members)


def _summary(employee: EmployeeRecord) -> EmployeeSummary:
    return EmployeeSummary(
        employee_id=employee.employee_id,
        employee_name=employee.employee_name,
        email=employee.email,
        department=employee.department,
    )


def resolve_hierarchy(
    employees: tuple[EmployeeRecord, ...],
) -> HierarchyAnalysis:
    """Resolve manager references and summarize the accepted hierarchy."""

    employee_by_id = {employee.employee_id: employee for employee in employees}
    employee_by_email = {employee.email: employee for employee in employees}

    roots: list[EmployeeSummary] = []
    issues: list[RowIssue] = []
    manager_by_employee: dict[str, str] = {}

    for employee in employees:
        if not employee.manager_id and not employee.manager_email:
            roots.append(_summary(employee))
            continue

        messages: list[str] = []
        manager: EmployeeRecord | None = None

        if employee.manager_id and employee.manager_email:
            manager_from_id = employee_by_id.get(employee.manager_id)
            manager_from_email = employee_by_email.get(employee.manager_email)

            if manager_from_id is None:
                messages.append(
                    f"Manager ID '{employee.manager_id}' was not found among accepted employees."
                )
            if manager_from_email is None:
                messages.append(
                    "Manager email "
                    f"'{employee.manager_email}' was not found among accepted employees."
                )
            if (
                manager_from_id is not None
                and manager_from_email is not None
                and manager_from_id.employee_id != manager_from_email.employee_id
            ):
                messages.append(
                    "Manager ID and manager email identify different employees."
                )
            elif manager_from_id is not None and manager_from_email is not None:
                manager = manager_from_id
        elif employee.manager_id:
            manager = employee_by_id.get(employee.manager_id)
            if manager is None:
                messages.append(
                    f"Manager ID '{employee.manager_id}' was not found among accepted employees."
                )
        else:
            manager = employee_by_email.get(employee.manager_email)
            if manager is None:
                messages.append(
                    "Manager email "
                    f"'{employee.manager_email}' was not found among accepted employees."
                )

        if manager is not None and manager.employee_id == employee.employee_id:
            messages.append("An employee cannot manage themselves.")

        if messages:
            issues.append(RowIssue(employee.source_row, tuple(messages)))
        elif manager is not None:
            manager_by_employee[employee.employee_id] = manager.employee_id

    direct_report_counts = Counter(manager_by_employee.values())
    # Preserve source order instead of sorting so this summarization remains O(n).
    managers = tuple(
        ManagerSummary(
            _summary(employee), direct_report_counts[employee.employee_id]
        )
        for employee in employees
        if employee.employee_id in direct_report_counts
    )

    cycle_ids = detect_cycle_members(manager_by_employee)
    cyclic_employees = tuple(
        _summary(employee)
        for employee in employees
        if employee.employee_id in cycle_ids
    )

    return HierarchyAnalysis(
        roots=tuple(roots),
        managers=managers,
        cyclic_employees=cyclic_employees,
        issues=tuple(issues),
    )


def analyze_csv(stream: TextIO) -> AnalysisResult:
    """Compose all pure pipeline stages into the result used by the web layer."""

    parsed = parse_csv(stream)
    identities = validate_identities(parsed.rows)
    hierarchy = resolve_hierarchy(identities.accepted)

    issue_by_source_row = {
        issue.source_row: issue
        for issue in (*identities.issues, *hierarchy.issues)
    }
    issues = tuple(
        issue_by_source_row[row.source_row]
        for row in parsed.rows
        if row.source_row in issue_by_source_row
    )

    return AnalysisResult(
        total_rows=parsed.total_rows,
        accepted_count=len(identities.accepted),
        issues=issues,
        roots=hierarchy.roots,
        managers=hierarchy.managers,
        cyclic_employees=hierarchy.cyclic_employees,
    )
