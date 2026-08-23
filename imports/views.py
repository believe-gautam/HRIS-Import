from __future__ import annotations

import io

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .analysis import AnalysisResult, CSVImportError, analyze_csv
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


def upload_preview(request: HttpRequest) -> HttpResponse:
    result: AnalysisResult | None = None

    if request.method == "POST":
        form = HRISUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                result = _analyze_upload(form.cleaned_data["csv_file"])
            except CSVImportError as exc:
                form.add_error("csv_file", str(exc))
    else:
        form = HRISUploadForm()

    return render(request, "imports/upload.html", {"form": form, "result": result})
