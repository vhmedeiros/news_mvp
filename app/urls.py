from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('vehicles/', include('veiculos.urls', namespace='vehicles')),
    path('news/', include('noticias.urls', namespace='news')),
    path('imports/', include('importacoes.urls', namespace='imports')),
    path('dashboard/', include('dashboard.urls', namespace='dashboard')),
    path('', RedirectView.as_view(url='/news/')),
]
