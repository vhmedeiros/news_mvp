from django.views.generic import ListView, DetailView
from .models import News

class NewsListView(ListView):
    model = News
    template_name = "news/news_list.html"
    context_object_name = "items"
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().select_related("vehicle", "section")
        v = self.request.GET.get("vehicle")
        if v:
            qs = qs.filter(vehicle_id=v)
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(title__icontains=q)
        return qs

class NewsDetailView(DetailView):
    model = News
    template_name = "news/news_detail.html"
    context_object_name = "item"