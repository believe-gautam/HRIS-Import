from django.urls import path

from .views import scan_detail, scan_history, scan_table_data, upload_preview


app_name = "imports"

urlpatterns = [
    path("", upload_preview, name="upload"),
    path("history/", scan_history, name="history"),
    path(
        "history/<int:scan_id>/data/<str:table_key>/",
        scan_table_data,
        name="scan_table_data",
    ),
    path("history/<int:scan_id>/", scan_detail, name="scan_detail"),
]
