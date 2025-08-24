# importacoes/scheduler.py
from threading import Thread, Event
import time
from django.utils import timezone
from django.db import close_old_connections

from .models import ImportConfig, ImportStatus
from .services import run_import

_started = False
_stop_event = Event()

def _due_configs():
    now = timezone.now()
    qs = ImportConfig.objects.filter(enabled=True)
    due = []
    for cfg in qs:
        if cfg.status == ImportStatus.RUNNING:
            continue
        last = cfg.last_run_at
        if last is None or (now - last).total_seconds() >= (cfg.interval_minutes or 20) * 60:
            due.append(cfg.id)
    return due

def _loop():
    while not _stop_event.is_set():
        try:
            close_old_connections()  # higiene p/ threads
            ids = _due_configs()
            for cid in ids:
                Thread(target=run_import, args=(cid,), daemon=True, name=f"import-{cid}").start()
        except Exception:
            # não matar o loop se algo der errado
            pass
        # aguarda 60s (pode reduzir se quiser mais responsivo)
        _stop_event.wait(60)

def start_scheduler():
    global _started
    if _started:
        return
    t = Thread(target=_loop, daemon=True, name="imports-scheduler")
    t.start()
    _started = True
