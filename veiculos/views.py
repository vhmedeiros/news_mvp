# veiculos/views.py
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from importacoes.models import ImportConfig
from noticias.models import News
from .models import Vehicle, MediaType, Status

class VehicleListView(ListView):
    model = Vehicle
    template_name = "vehicles/vehicle_list.html"
    context_object_name = "vehicles"
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(name__icontains=q)
        media_type = self.request.GET.get("media_type")
        if media_type:
            qs = qs.filter(media_type=media_type)
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Envie as choices prontas para o template
        ctx["media_type_choices"] = MediaType.choices
        ctx["status_choices"] = Status.choices
        return ctx

class VehicleDetailView(DetailView):
    model = Vehicle
    template_name = "vehicles/vehicle_detail.html"
    context_object_name = "vehicle"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        v = self.object
        # contadores
        from veiculos.models import Section
        ctx["counts"] = {
            "sections": Section.objects.filter(vehicle=v).count(),
            "imports": ImportConfig.objects.filter(vehicle=v).count(),
            "news": News.objects.filter(vehicle=v).count(),
        }
        # listas compactas
        ctx["recent_imports"] = (ImportConfig.objects
                                 .filter(vehicle=v).order_by("-last_run_at")[:5])
        ctx["recent_news"] = (News.objects
                              .filter(vehicle=v).order_by("-captured_at")[:5])
        return ctx

class VehicleCreateView(CreateView):
    model = Vehicle
    template_name = "vehicles/vehicle_form.html"
    fields = ["name","media_type","status","country","state","city","url","notes"]
    success_url = reverse_lazy("vehicles:vehicle-list")

class VehicleUpdateView(UpdateView):
    model = Vehicle
    template_name = "vehicles/vehicle_form.html"
    fields = ["name","media_type","status","country","state","city","url","notes"]
    success_url = reverse_lazy("vehicles:vehicle-list")


class VehicleDeleteView(DeleteView):
    model = Vehicle
    template_name = "vehicles/vehicle_confirm_delete.html"
    success_url = reverse_lazy("vehicles:vehicle-list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # importa aqui para evitar ciclos
        from importacoes.models import ImportConfig
        from noticias.models import News
        from veiculos.models import Section

        obj = self.object
        ctx["counts"] = {
            "sections": Section.objects.filter(vehicle=obj).count(),
            "imports": ImportConfig.objects.filter(vehicle=obj).count(),
            "news": News.objects.filter(vehicle=obj).count(),
        }
        return ctx