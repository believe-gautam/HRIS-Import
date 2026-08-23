"""SQLite persistence kept outside the pure HRIS analysis core."""

from __future__ import annotations

from itertools import chain, islice
from pathlib import PurePosixPath
from typing import Iterable, Iterator, TypeVar

from django.db import transaction

from .analysis import (
    AnalysisResult,
    EmployeeSummary,
)
from .models import ImportScan, ScanEmployeeDetail, ScanIssue


BULK_BATCH_SIZE = 1_000
StoredModel = TypeVar("StoredModel", ScanIssue, ScanEmployeeDetail)


def _batches(values: Iterable[StoredModel]) -> Iterator[list[StoredModel]]:
    iterator = iter(values)
    while batch := list(islice(iterator, BULK_BATCH_SIZE)):
        yield batch


def _safe_filename(filename: str) -> str:
    basename = PurePosixPath(filename.replace("\\", "/")).name
    return (basename or "upload.csv")[:255]


def _stored_employee(
    *,
    scan: ImportScan,
    category: str,
    position: int,
    employee: EmployeeSummary,
    direct_report_count: int | None = None,
) -> ScanEmployeeDetail:
    return ScanEmployeeDetail(
        scan=scan,
        category=category,
        position=position,
        employee_id=employee.employee_id,
        employee_name=employee.employee_name,
        email=employee.email,
        department=employee.department,
        direct_report_count=direct_report_count,
    )


@transaction.atomic
def save_analysis_result(
    result: AnalysisResult,
    *,
    original_filename: str,
) -> ImportScan:
    """Persist one completed analysis with batched inserts inside one transaction."""

    scan = ImportScan.objects.create(
        original_filename=_safe_filename(original_filename),
        total_rows=result.total_rows,
        accepted_count=result.accepted_count,
        error_count=len(result.issues),
        root_count=len(result.roots),
        manager_count=len(result.managers),
        cycle_count=len(result.cyclic_employees),
    )

    stored_issues = (
        ScanIssue(
            scan=scan,
            position=position,
            source_row=issue.source_row,
            messages=list(issue.messages),
            search_text="\n".join(issue.messages),
        )
        for position, issue in enumerate(result.issues)
    )
    for batch in _batches(stored_issues):
        ScanIssue.objects.bulk_create(batch, batch_size=BULK_BATCH_SIZE)

    root_details = (
        _stored_employee(
            scan=scan,
            category=ScanEmployeeDetail.Category.ROOT,
            position=position,
            employee=employee,
        )
        for position, employee in enumerate(result.roots)
    )
    manager_details = (
        _stored_employee(
            scan=scan,
            category=ScanEmployeeDetail.Category.MANAGER,
            position=position,
            employee=manager.employee,
            direct_report_count=manager.direct_report_count,
        )
        for position, manager in enumerate(result.managers)
    )
    cycle_details = (
        _stored_employee(
            scan=scan,
            category=ScanEmployeeDetail.Category.CYCLE,
            position=position,
            employee=employee,
        )
        for position, employee in enumerate(result.cyclic_employees)
    )
    for batch in _batches(chain(root_details, manager_details, cycle_details)):
        ScanEmployeeDetail.objects.bulk_create(batch, batch_size=BULK_BATCH_SIZE)

    return scan
