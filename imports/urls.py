from django.urls import path

from .views import upload_preview


app_name = "imports"

urlpatterns = [path("", upload_preview, name="upload")]
