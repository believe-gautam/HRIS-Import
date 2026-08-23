"""Database-backed result-table filtering, sorting, and pagination."""

from __future__ import annotations

from collections.abc import Mapping

from django.core.paginator import Paginator
from django.db.models import F, Q, QuerySet

from .models import ImportScan, ScanEmployeeDetail, ScanIssue


PAGE_SIZES = frozenset({10, 25, 50, 100})
TABLE_KEYS = ("issues", "roots", "managers", "cycles")
CATEGORY_BY_TABLE = {
    "roots": ScanEmployeeDetail.Category.ROOT,
    "managers": ScanEmployeeDetail.Category.MANAGER,
    "cycles": ScanEmployeeDetail.Category.CYCLE,
}


def _positive_int(value: str | None, default: int) -> int:
    try:
        parsed = int(value or "")
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _ordered(
    queryset: QuerySet,
    *,
    sort_key: str,
    direction: str,
    allowed_sorts: Mapping[str, tuple[str, str]],
) -> QuerySet:
    if sort_key not in allowed_sorts:
        return queryset.order_by("position")

    field_name, _field_type = allowed_sorts[sort_key]
    expression = F(field_name)
    if direction == "descending":
        expression = expression.desc(nulls_last=True)
    else:
        expression = expression.asc(nulls_first=True)
    return queryset.order_by(expression, "position")


def _issue_queryset(
    scan: ImportScan,
    *,
    query: str,
    sort_key: str,
    direction: str,
) -> QuerySet[ScanIssue]:
    issues = ScanIssue.objects.filter(scan=scan)
    if query:
        criteria = Q(search_text__icontains=query)
        if query.isdigit():
            criteria |= Q(source_row=int(query))
        issues = issues.filter(criteria)

    return _ordered(
        issues,
        sort_key=sort_key,
        direction=direction,
        allowed_sorts={
            "source_row": ("source_row", "number"),
            "messages": ("search_text", "text"),
        },
    )


def _employee_queryset(
    scan: ImportScan,
    *,
    table_key: str,
    query: str,
    sort_key: str,
    direction: str,
) -> QuerySet[ScanEmployeeDetail]:
    employees = ScanEmployeeDetail.objects.filter(
        scan=scan,
        category=CATEGORY_BY_TABLE[table_key],
    )
    if query:
        criteria = (
            Q(employee_id__icontains=query)
            | Q(employee_name__icontains=query)
            | Q(email__icontains=query)
        )
        if table_key == "managers":
            if query.isdigit():
                criteria |= Q(direct_report_count=int(query))
        else:
            criteria |= Q(department__icontains=query)
        employees = employees.filter(criteria)

    allowed_sorts = {
        "employee_id": ("employee_id", "text"),
        "employee_name": ("employee_name", "text"),
        "email": ("email", "text"),
    }
    if table_key == "managers":
        allowed_sorts["direct_report_count"] = ("direct_report_count", "number")
    else:
        allowed_sorts["department"] = ("department", "text")

    return _ordered(
        employees,
        sort_key=sort_key,
        direction=direction,
        allowed_sorts=allowed_sorts,
    )


def _serialize_issue(issue: ScanIssue) -> dict[str, object]:
    return {
        "source_row": issue.source_row,
        "messages": issue.messages,
    }


def _serialize_employee(
    employee: ScanEmployeeDetail,
    *,
    table_key: str,
) -> dict[str, object]:
    row: dict[str, object] = {
        "employee_id": employee.employee_id,
        "employee_name": employee.employee_name,
        "email": employee.email,
    }
    if table_key == "managers":
        row["direct_report_count"] = employee.direct_report_count
    else:
        row["department"] = employee.department
    return row


def get_table_page(
    scan: ImportScan,
    table_key: str,
    params: Mapping[str, str],
) -> dict[str, object]:
    """Return one bounded result page; no full result collection is materialized."""

    if table_key not in TABLE_KEYS:
        raise ValueError(f"Unknown result table: {table_key}")

    query = (params.get("q") or "").strip()
    sort_key = params.get("sort") or ""
    direction = (
        "descending" if params.get("direction") == "descending" else "ascending"
    )
    requested_size = _positive_int(params.get("page_size"), 25)
    page_size = requested_size if requested_size in PAGE_SIZES else 25

    if table_key == "issues":
        queryset = _issue_queryset(
            scan,
            query=query,
            sort_key=sort_key,
            direction=direction,
        )
    else:
        queryset = _employee_queryset(
            scan,
            table_key=table_key,
            query=query,
            sort_key=sort_key,
            direction=direction,
        )

    paginator = Paginator(queryset, page_size)
    page = paginator.get_page(_positive_int(params.get("page"), 1))
    if table_key == "issues":
        rows = [_serialize_issue(issue) for issue in page.object_list]
    else:
        rows = [
            _serialize_employee(employee, table_key=table_key)
            for employee in page.object_list
        ]

    return {
        "rows": rows,
        "page": page.number if paginator.count else 0,
        "page_count": paginator.num_pages if paginator.count else 0,
        "page_size": page_size,
        "total": paginator.count,
        "first": page.start_index(),
        "last": page.end_index(),
        "query": query,
        "sort": sort_key,
        "direction": direction,
    }
