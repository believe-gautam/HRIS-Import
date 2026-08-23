from __future__ import annotations

import io

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .analysis import (
    AnalysisResult,
    CSVImportError,
    EmployeeSummary,
    analyze_csv,
)
from .forms import HRISUploadForm


def _analyze_upload(uploaded_file) -> AnalysisResult:
    """Adapt Django's binary upload to the analysis core's text stream."""

    uploaded_file.seek(0)
    text_stream = io.TextIOWrapper(
        uploaded_file.file,
        encoding="utf-8-sig",
        newline="",
    )
    try:
        return analyze_csv(text_stream)
    finally:
        # Django owns and closes the underlying upload.
        text_stream.detach()


def _employee_payload(employee: EmployeeSummary) -> dict[str, str]:
    return {
        "employee_id": employee.employee_id,
        "employee_name": employee.employee_name,
        "email": employee.email,
        "department": employee.department,
    }


def _table_payload(result: AnalysisResult) -> dict[str, list[dict[str, object]]]:
    """Return the safe, JSON-serializable rows used by the data-table shell."""

    return {
        "issues": [
            {
                "source_row": issue.source_row,
                "messages": list(issue.messages),
            }
            for issue in result.issues
        ],
        "roots": [_employee_payload(employee) for employee in result.roots],
        "managers": [
            {
                "employee_id": manager.employee.employee_id,
                "employee_name": manager.employee.employee_name,
                "email": manager.employee.email,
                "direct_report_count": manager.direct_report_count,
            }
            for manager in result.managers
        ],
        "cycles": [
            _employee_payload(employee) for employee in result.cyclic_employees
        ],
    }


def upload_preview(request: HttpRequest) -> HttpResponse:
    result: AnalysisResult | None = None
    table_data: dict[str, list[dict[str, object]]] | None = None

    if request.method == "POST":
        form = HRISUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                result = _analyze_upload(form.cleaned_data["csv_file"])
                table_data = _table_payload(result)
            except CSVImportError as exc:
                form.add_error("csv_file", str(exc))
    else:
        form = HRISUploadForm()

    return render(
        request,
        "imports/upload.html",
        {"form": form, "result": result, "table_data": table_data},
    )
