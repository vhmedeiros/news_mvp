from django.urls import path
from .views import (
    ImportConfigListView, ImportConfigCreateView, ImportConfigUpdateView,
    ImportConfigDetailView, ImportJobDetailView, run_now, run_all
)

app_name = "imports"   # <-- ESSENCIAL

urlpatterns = [
    path("", ImportConfigListView.as_view(), name="import-list"),
    path("create/", ImportConfigCreateView.as_view(), name="import-create"),
    path("<int:pk>/", ImportConfigDetailView.as_view(), name="import-detail"),
    path("<int:pk>/edit/", ImportConfigUpdateView.as_view(), name="import-update"),
    path("<int:pk>/run/", run_now, name="import-run"),
    path("job/<int:pk>/", ImportJobDetailView.as_view(), name="job-detail"),
    path("run-all/", run_all, name="import-run-all"),
]
