from django.urls import path
from .views import VehicleListView, VehicleDetailView, VehicleCreateView, VehicleUpdateView, VehicleDeleteView

app_name = "vehicles"

urlpatterns = [
    path("", VehicleListView.as_view(), name="vehicle-list"),
    path("create/", VehicleCreateView.as_view(), name="vehicle-create"),
    path("<int:pk>/", VehicleDetailView.as_view(), name="vehicle-detail"),
    path("<int:pk>/edit/", VehicleUpdateView.as_view(), name="vehicle-update"),
    path("<int:pk>/delete/", VehicleDeleteView.as_view(), name="vehicle-delete"),
]
