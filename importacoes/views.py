import threading
import json
import re
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.shortcuts import redirect, get_object_or_404
from collections import Counter, defaultdict
from .models import ImportConfig, ImportJob, ImportStatus
from .forms import ImportConfigForm
from .services import run_import

class ImportConfigListView(ListView):
    model = ImportConfig
    template_name = "imports/import_list.html"
    context_object_name = "items"
    paginate_by = 20

class ImportConfigDetailView(DetailView):
    model = ImportConfig
    template_name = "imports/import_detail.html"
    context_object_name = "item"

class ImportConfigCreateView(CreateView):
    model = ImportConfig
    form_class = ImportConfigForm
    template_name = "imports/import_form.html"

    def form_valid(self, form):
        resp = super().form_valid(form)
        # redireciona para executar
        return redirect("imports:import-run", pk=self.object.pk)
class ImportConfigUpdateView(UpdateView):
    model = ImportConfig
    form_class = ImportConfigForm
    template_name = "imports/import_form.html"
    success_url = reverse_lazy("imports:import-list")

def run_now(request, pk: int):
    cfg = get_object_or_404(ImportConfig, pk=pk)
    t = threading.Thread(target=run_import, args=(cfg.id,), daemon=True)
    t.start()
    messages.success(request, f"Import '{cfg.name}' started.")
    return redirect("imports:import-list")


class ImportJobDetailView(DetailView):
    model = ImportJob
    template_name = "imports/job_detail.html"
    context_object_name = "job"


def run_all(request):
    cfg_ids = list(ImportConfig.objects.filter(enabled=True).values_list("id", flat=True))
    for cid in cfg_ids:
        threading.Thread(target=run_import, args=(cid,), daemon=True).start()
    messages.success(request, f"Started {len(cfg_ids)} import(s).")
    return redirect("imports:import-list")


# -------------------- FALLBACK p/ logs texto (já tínhamos) --------------------
def parse_legacy_log_to_events(text: str) -> dict:
    if not text:
        return {"events": []}
    events = []
    ts_re = re.compile(r"^\[(?P<ts>\d{2}:\d{2}:\d{2})\]\s*")
    url_re = re.compile(r"(https?://\S+)")
    stage_re = re.compile(r"\[(?P<stage>[a-zA-Z0-9_\-]+)\]")
    xp_tail = re.compile(r"\|\s*(?P<xp>//.+)$")

    current_article = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m_ts = ts_re.match(line)
        ts = m_ts.group("ts") if m_ts else None
        body = line[m_ts.end():].strip() if m_ts else line
        low = body.lower()

        level = "info"
        if "falha" in low or "error" in low or "exception" in low or "traceback" in low:
            level = "error"
        elif "warn" in low or "aviso" in low:
            level = "warn"
        elif "skip" in low or "ignorado" in low:
            level = "skip"
        elif "xpath ok" in low or "get 200" in low or "ok" in low:
            level = "ok"

        m_st = stage_re.search(body)
        stage = (m_st.group("stage") if m_st else None) or (
            "xpath" if "xpath" in low else "http-get" if "get 200" in low else "log"
        )

        m_url = url_re.search(body)
        url = m_url.group(1) if m_url else None
        if url:
            current_article = url

        m_xp = xp_tail.search(body)
        xp = m_xp.group("xp").strip() if m_xp else None

        events.append({
            "level": level,
            "stage": stage,
            "ts": ts,
            "msg": body,
            "url": url or current_article,
            "xpath": xp,
            "article_url": current_article,
        })
    return {"events": events}

# -------------------- NOVOS PARSERS TOLERANTES --------------------------------
def _split_json_objects(s: str):
    """Se o log veio como {...}{...}{...}, separa objetos balanceando chaves."""
    objs = []
    depth = 0
    start = None
    in_str = False
    esc = False
    for i, ch in enumerate(s):
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                objs.append(s[start:i+1])
                start = None
    return objs

def _parse_log_any(job_log: str):
    """Aceita dict{'events':...}, list, JSONL e objetos concatenados."""
    if not job_log:
        return []

    # 1) dict ou list
    try:
        data = json.loads(job_log)
        if isinstance(data, dict) and isinstance(data.get("events"), list):
            return data["events"]
        if isinstance(data, list):
            return data
    except Exception:
        pass

    # 2) JSON lines (um objeto por linha)
    events = []
    has_jsonl = False
    for line in job_log.splitlines():
        t = line.strip()
        if not (t.startswith("{") and t.endswith("}")):
            continue
        try:
            events.append(json.loads(t))
            has_jsonl = True
        except Exception:
            pass
    if has_jsonl and events:
        return events

    # 3) Objetos concatenados {...}{...}{...}
    parts = _split_json_objects(job_log)
    for p in parts:
        try:
            events.append(json.loads(p))
        except Exception:
            continue
    if events:
        return events

    # 4) Por fim: parser heurístico de texto
    return parse_legacy_log_to_events(job_log).get("events", [])

# -------------------- VIEW -----------------------------------------------------
class ImportJobDetailView(DetailView):
    model = ImportJob
    template_name = "imports/job_detail.html"
    context_object_name = "job"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        job = self.object

        events = _parse_log_any(job.log or "")

        # Se mesmo assim não deu, cai para plain_log (último recurso)
        if not events:
            ctx["plain_log"] = job.log
            return ctx

        # Filtro: por padrão só ERROS; ?level=all mostra tudo
        filter_level = (self.request.GET.get("level") or "error").lower()
        only_errors = filter_level != "all"
        def visible(e): return (e.get("level") == "error") if only_errors else True

        # Normalização leve (caso alguns produtores usem 'where'/'article'):
        for e in events:
            if not e.get("stage") and e.get("where"):
                e["stage"] = e.get("where")
            if not e.get("article_url") and e.get("url") and e.get("stage") in {"article", "article-title", "article-content", "article-date", "article-section-name", "article-subtitle", "article-author"}:
                e["article_url"] = e["url"]

        # Contagens e agrupamentos
        level_counts_all = Counter(ev.get("level", "info") for ev in events)
        level_counts = Counter(ev.get("level", "info") for ev in events if visible(ev))
        stage_counts = Counter(ev.get("stage") for ev in events if ev.get("stage") and visible(ev))

        events_geral = [ev for ev in events if not ev.get("article_url") and visible(ev)]

        by_article = defaultdict(list)
        for ev in events:
            aurl = ev.get("article_url")
            if aurl and visible(ev):
                by_article[aurl].append(ev)

        artigos = []
        for aurl, evs in by_article.items():
            title = next((x.get("article_title") for x in evs if x.get("article_title")), None)
            artigos.append({"url": aurl, "title": title, "events": evs})

        artigos.sort(key=lambda a: (-sum(1 for ev in a["events"] if ev.get("level") == "error"), (a["title"] or "")))

        ctx.update({
            "only_errors": only_errors,
            "events_geral": events_geral,
            "artigos": artigos,
            "stage_counts": dict(stage_counts),
            "level_counts": dict(level_counts),
            "level_counts_all": dict(level_counts_all),
            "plain_log": None,  # força o template bonito
        })
        return ctx
