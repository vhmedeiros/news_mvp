# importacoes/apps.py
from django.apps import AppConfig
import os

class ImportacoesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'importacoes'

    def ready(self):
        # Evita rodar 2x com o autoreloader do runserver
        if os.environ.get("RUN_MAIN") != "true":
            return
        try:
            from .scheduler import start_scheduler
            start_scheduler()
        except Exception:
            # evitar crash na inicialização por erro no scheduler
            pass
