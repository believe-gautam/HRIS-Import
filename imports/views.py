from __future__ import annotations

import io

from django.core.paginator import Paginator
from django.db.models import Q, QuerySet
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .analysis import AnalysisResult, CSVImportError, analyze_csv
from .forms import HRISUploadForm
from .models import ImportScan
from .persistence import save_analysis_result
from .tables import TABLE_KEYS, get_table_page


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


def upload_preview(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = HRISUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                result = _analyze_upload(form.cleaned_data["csv_file"])
                saved_scan = save_analysis_result(
                    result,
                    original_filename=form.cleaned_data["csv_file"].name,
                )
                return redirect("imports:scan_detail", scan_id=saved_scan.id)
            except CSVImportError as exc:
                form.add_error("csv_file", str(exc))
    else:
        form = HRISUploadForm()

    return render(request, "imports/upload.html", {"form": form})


def _filtered_scan_history(request: HttpRequest) -> tuple[QuerySet[ImportScan], str, str]:
    search = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "newest")
    sort_fields = {
        "newest": ("-created_at", "-id"),
        "oldest": ("created_at", "id"),
        "filename": ("original_filename", "-created_at"),
        "largest": ("-total_rows", "-created_at"),
        "errors": ("-error_count", "-created_at"),
    }
    if sort not in sort_fields:
        sort = "newest"

    scans = ImportScan.objects.all()
    if search:
        criteria = Q(original_filename__icontains=search)
        if search.isdigit():
            criteria |= Q(id=int(search))
        scans = scans.filter(criteria)

    return scans.order_by(*sort_fields[sort]), search, sort


def scan_history(request: HttpRequest) -> HttpResponse:
    scans, search, sort = _filtered_scan_history(request)
    page = Paginator(scans, 20).get_page(request.GET.get("page"))
    history_pages = [
        {
            "number": item if isinstance(item, int) else None,
            "label": str(item),
            "current": item == page.number,
        }
        for item in page.paginator.get_elided_page_range(
            page.number,
            on_each_side=1,
            on_ends=1,
        )
    ]
    return render(
        request,
        "imports/history.html",
        {
            "history_pages": history_pages,
            "page": page,
            "search": search,
            "sort": sort,
        },
    )


def scan_detail(request: HttpRequest, scan_id: int) -> HttpResponse:
    scan = get_object_or_404(ImportScan, pk=scan_id)
    initial_pages = {
        table_key: get_table_page(scan, table_key, {}) for table_key in TABLE_KEYS
    }
    return render(
        request,
        "imports/scan_detail.html",
        {"scan": scan, "initial_pages": initial_pages},
    )


def scan_table_data(
    request: HttpRequest,
    scan_id: int,
    table_key: str,
) -> JsonResponse:
    scan = get_object_or_404(ImportScan, pk=scan_id)
    try:
        page = get_table_page(scan, table_key, request.GET)
    except ValueError as exc:
        raise Http404(str(exc)) from exc
    return JsonResponse(page)
