# dashboard/views.py
from __future__ import annotations

from datetime import datetime, timedelta
from django.db.models import Count
from django.db.models.functions import TruncDay, TruncMonth, TruncYear, Coalesce
from django.utils import timezone
from django.views.generic import TemplateView

from noticias.models import News
from veiculos.models import Vehicle

TOP_N = 8
MAX_DAYS = 365 * 2  # limite de 2 anos por requisição

class DashboardView(TemplateView):
    template_name = "dashboard/index.html"

    def _parse_date(self, s: str | None):
        if not s:
            return None
        try:
            # padroniza para timezone atual e meia-noite
            d = datetime.strptime(s, "%Y-%m-%d")
            return timezone.make_aware(d, timezone.get_current_timezone())
        except Exception:
            return None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        g = (self.request.GET.get("g") or "day").lower()
        if g not in {"day", "month", "year"}:
            g = "day"

        now = timezone.now()

        # --- intervalo por GET (from/to) ou padrão por granularidade
        dfrom = self._parse_date(self.request.GET.get("from"))
        dto   = self._parse_date(self.request.GET.get("to"))

        if dfrom and dto and dfrom > dto:
            # troca se vier invertido
            dfrom, dto = dto, dfrom

        if not dfrom or not dto:
            if g == "day":
                dfrom = now - timedelta(days=6)   # últimos 7 dias
                dto   = now
            elif g == "month":
                dfrom = now - timedelta(days=30*5)  # ~6 meses
                dto   = now
            else:
                dfrom = now - timedelta(days=365*2) # ~2 anos
                dto   = now

        # limita range
        if (dto - dfrom).days > MAX_DAYS:
            dfrom = dto - timedelta(days=MAX_DAYS)

        # define função de trunc conforme granularidade
        if g == "day":
            trunc, fmt = TruncDay, "%d/%m"
        elif g == "month":
            trunc, fmt = TruncMonth, "%m/%Y"
        else:
            trunc, fmt = TruncYear, "%Y"

        # campo de data para agregação: published_at OU captured_at
        dt_field = Coalesce("published_at", "captured_at")

        # --- Série temporal
        qs_series = (
            News.objects
            .filter(captured_at__range=(dfrom, dto))
            .annotate(period=trunc(dt_field))
            .values("period")
            .annotate(total=Count("id"))
            .order_by("period")
        )

        series_labels, series_data = [], []
        for row in qs_series:
            if row["period"]:
                series_labels.append(row["period"].strftime(fmt))
                series_data.append(int(row["total"]))

        total_interval = int(sum(series_data))

        # --- Ranking (top N)
        qs_top = (
            News.objects
            .filter(captured_at__range=(dfrom, dto))
            .values("vehicle__name")
            .annotate(total=Count("id"))
            .order_by("-total")[:TOP_N]
        )
        rank_labels = [r["vehicle__name"] for r in qs_top]
        rank_data   = [int(r["total"]) for r in qs_top]

        # --- Por tipo de veículo
        media_map = dict(Vehicle._meta.get_field("media_type").choices)
        qs_types = (
            News.objects
            .filter(captured_at__range=(dfrom, dto))
            .values("vehicle__media_type")
            .annotate(total=Count("id"))
            .order_by("-total")
        )
        type_labels = [media_map.get(r["vehicle__media_type"], r["vehicle__media_type"] or "—") for r in qs_types]
        type_data   = [int(r["total"]) for r in qs_types]

        ctx.update({
            "granularity": g,
            "start": dfrom, "end": dto,
            "series_labels": series_labels, "series_data": series_data,
            "rank_labels": rank_labels,     "rank_data": rank_data,
            "type_labels": type_labels,     "type_data": type_data,
            "total_interval": total_interval,
            "total_news": News.objects.count(),
            "total_vehicles": Vehicle.objects.count(),
        })
        return ctx
