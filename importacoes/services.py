# importacoes/services.py
from __future__ import annotations

import re
import json
import concurrent.futures
import traceback
from datetime import datetime
from urllib.parse import urljoin

import requests
from lxml import html
from dateutil import parser as dateparser

from django.db import transaction
from django.utils import timezone

from veiculos.models import Section
from noticias.models import News
from .models import ImportConfig, ImportJob, ImportStatus


# =============================================================================
# HTTP utilitário
# =============================================================================

DEFAULT_HEADERS = {
    "User-Agent": "NewsScraperEdu/1.0 (+https://example.local)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def _fetch(url: str, timeout: int = 25) -> html.HtmlElement:
    """
    Faz GET e devolve um HtmlElement (lxml). Levanta HTTPError p/ status != 200.
    """
    resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    resp.raise_for_status()
    return html.fromstring(resp.content)


# =============================================================================
# Helpers de XPath e texto
# =============================================================================

def _text(nodes, default: str = "") -> str:
    """
    Concatena o texto de uma lista de nós/strings, já com trim e remoção de vazio.
    """
    if not nodes:
        return default
    parts: list[str] = []
    for n in nodes:
        if isinstance(n, str):
            s = n.strip()
            if s:
                parts.append(s)
        elif hasattr(n, "text_content"):
            s = n.text_content().strip()
            if s:
                parts.append(s)
    return " ".join(parts).strip()

def _strings_from_nodes(nodes) -> list[str]:
    """
    Extrai hrefs/strings a partir de resultados de XPath (string ou elemento).
    """
    out: list[str] = []
    for n in nodes:
        if isinstance(n, str):
            s = n.strip()
            if s:
                out.append(s)
        else:
            href = n.get("href")
            if href:
                out.append(href)
            else:
                inner = n.xpath(".//@href")
                if inner:
                    out.append(inner[0])
    return out


# =============================================================================
# Logger estruturado (vai para job.log como JSON)
#   - Seguro: nunca derruba a importação por erro de log.
#   - Convenção de níveis: info | ok | warn | skip | error
#   - 'stage' é SEMPRE keyword-only (obrigatório passar como stage="...")
# =============================================================================

class JsonLogger:
    def __init__(self):
        self.events = []

    def _event(self, level, msg, *, stage=None, url=None, xpath=None, **extra):
        return {
            "level": level,                          # 'info' | 'ok' | 'warn' | 'skip' | 'error'
            "msg": str(msg).strip(),
            "stage": stage or "",
            "url": url or "",
            "xpath": xpath or "",
            "ts": datetime.now().strftime("%H:%M:%S"),
            **({k: v for k, v in extra.items() if v is not None}),
        }

    def _safe_append(self, ev):
        try:
            self.events.append(ev)
        except Exception as e:
            # Não deixa o logger quebrar a execução
            self.events.append({
                "level": "error",
                "msg": f"[logger-fail] {type(e).__name__}: {e}",
                "stage": "logger",
                "ts": datetime.now().strftime("%H:%M:%S"),
            })

    # A partir daqui, 'stage' é keyword-only graças ao "*"
    def info(self, msg, *, stage=None, **extra): self._safe_append(self._event("info", msg, stage=stage, **extra))
    def ok  (self, msg, *, stage=None, **extra): self._safe_append(self._event("ok"  , msg, stage=stage, **extra))
    def warn(self, msg, *, stage=None, **extra): self._safe_append(self._event("warn", msg, stage=stage, **extra))
    def skip(self, msg, *, stage=None, **extra): self._safe_append(self._event("skip", msg, stage=stage, **extra))

    def error(self, msg, *, stage=None, exc: Exception | None = None, **extra):
        # Inclui tipo e traceback curto se for exceção Python
        if exc is not None and "trace" not in extra:
            extra["trace"] = traceback.format_exc(limit=6)
            extra["exc_type"] = type(exc).__name__
        self._safe_append(self._event("error", msg, stage=stage, **extra))


# =============================================================================
# Parser de data PT-BR tolerante (robusto a ruídos comuns)
# =============================================================================

PT_WEEKDAYS = [
    "segunda", "segunda-feira", "terca", "terça", "terça-feira",
    "quarta", "quarta-feira", "quinta", "quinta-feira",
    "sexta", "sexta-feira", "sabado", "sábado", "domingo",
]

PT_MONTHS = {
    r"janeiro|jan": "January",
    r"fevereiro|fev": "February",
    r"mar[cç]o|mar": "March",
    r"abril|abr": "April",
    r"maio|mai": "May",
    r"junho|jun": "June",
    r"julho|jul": "July",
    r"agosto|ago": "August",
    r"setembro|set": "September",
    r"outubro|out": "October",
    r"novembro|nov": "November",
    r"dezembro|dez": "December",
}

_CLEAN_TAIL = [
    r"\batualizado[:\s]*.*$",  # remove tudo após "Atualizado:"
    r"\bpublicado[:\s]*.*$",
    r"\|\s*.*$",               # barra vertical e o resto
    r"–\s*.*$", r"—\s*.*$",    # travessão e o resto
]

def parse_news_datetime(raw: str) -> datetime | None:
    """
    Converte variações PT-BR para datetime "aware".
    Ex.: 'Quarta-Feira, 20 de Agosto de 2025, 11h:30 | Atualizado: ...'
         '20/08/2025 14:03', '2025-08-21T14:03-04:00', '21 ago 2025 10h'
    """
    if not raw:
        return None

    txt = " ".join(str(raw).strip().split())
    low = txt

    # 1) corta cauda (Atualizado:, pipes, travessão)
    for pat in _CLEAN_TAIL:
        low = re.sub(pat, "", low, flags=re.IGNORECASE).strip()

    # 2) remove dia da semana
    for wd in PT_WEEKDAYS:
        low = re.sub(rf"\b{wd}\b,?", "", low, flags=re.IGNORECASE)

    # 3) normaliza conectores/horários
    low = re.sub(r"\bàs\b|\bas\b", " ", low, flags=re.IGNORECASE)
    low = re.sub(r"\bde\b", " ", low, flags=re.IGNORECASE)
    low = re.sub(r"(\d{1,2})h[:]?(\d{2})", r"\1:\2", low)  # 11h30 / 11h:30 -> 11:30
    low = re.sub(r"(\d{1,2})h(?!\d)", r"\1:00", low)       # 11h -> 11:00

    # 4) meses PT -> EN (dateutil entende melhor)
    for pt_regex, en in PT_MONTHS.items():
        low = re.sub(rf"\b({pt_regex})\b", en, low, flags=re.IGNORECASE)

    candidate = " ".join(low.split(",")).strip()

    # 5) tenta com dateutil
    dt = None
    try:
        dt = dateparser.parse(candidate, dayfirst=True, fuzzy=True)
    except Exception:
        dt = None

    # 6) fallback dd/mm/aaaa (c/ hora opcional)
    if dt is None:
        m = re.search(
            r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
            candidate,
        )
        if m:
            d, mth, y, hh, mm, ss = m.groups()
            y = int("20" + y) if len(y) == 2 else int(y)
            hh = int(hh) if hh else 0
            mm = int(mm) if mm else 0
            ss = int(ss) if ss else 0
            try:
                dt = datetime(y, int(mth), int(d), hh, mm, ss)
            except Exception:
                dt = None

    if dt:
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
    return None


# =============================================================================
# XPaths genéricos de fallback
# =============================================================================

GENERIC_LISTING_XPATHS = [
    "//article//a/@href",
    "//h2//a/@href",
    "//h3//a/@href",
    "//a[contains(@href,'/noticia') or contains(@href,'/news') or contains(@href,'/materia')]/@href",
]

GENERIC_CONTENT_XPATHS = [
    "//article//p",
    "//main//p",
    "//*[contains(@class,'content') or contains(@class,'article')]//p",
]

META_DATE_FALLBACKS = [
    "//meta[@property='article:published_time']/@content",
    "//meta[@itemprop='datePublished']/@content",
    "//meta[@name='pubdate']/@content",
    "//time/@datetime",
    "//*[contains(@class,'date')][1]",
]


# =============================================================================
# Execução da importação
# =============================================================================

def run_import(config_id: int, max_workers: int = 8, timeout: int = 25) -> ImportJob:
    """
    Executa uma importação completa e retorna o Job criado.
    Salva o log estruturado (JSON) em ImportJob.log.
    """
    config = ImportConfig.objects.select_related("vehicle").get(pk=config_id)

    job = ImportJob.objects.create(config=config, status=ImportStatus.RUNNING)
    log = JsonLogger()
    log.info(f"Início da importação: '{config.name}'", stage="start", url=config.vehicle.url)

    # Atualiza status da config
    config.status = ImportStatus.RUNNING
    config.last_run_at = timezone.now()
    config.save(update_fields=["status", "last_run_at"])

    found_links: set[str] = set()
    new_count = 0

    try:
        # ---------------------------------------------------------------------
        # 0) Homepage
        # ---------------------------------------------------------------------
        try:
            root = _fetch(config.vehicle.url, timeout=timeout)
            log.ok("GET 200 (homepage)", stage="http-get", url=config.vehicle.url)
        except requests.exceptions.HTTPError as e:
            code = getattr(e.response, "status_code", "?")
            log.error(f"HTTP {code} ao acessar homepage", stage="http-get", url=config.vehicle.url, exc=e)
            raise
        except Exception as e:
            log.error("Falha ao carregar homepage", stage="http-get", url=config.vehicle.url, exc=e)
            raise

        # ---------------------------------------------------------------------
        # 1) Editorias (opcional)
        # ---------------------------------------------------------------------
        editorial_urls: set[str] = set()
        lines = [l.strip() for l in (config.editorial_xpaths or "").splitlines() if l.strip()]

        if lines:
            for xp in lines:
                try:
                    nodes = root.xpath(xp)
                    hrefs = _strings_from_nodes(nodes)
                    for h in hrefs:
                        editorial_urls.add(urljoin(config.vehicle.url, h))
                    log.ok(f"Editorias encontradas: {len(hrefs)}", stage="editorial", xpath=xp)
                except Exception as e:
                    log.error("Falha ao executar XPath de editoria", stage="editorial", xpath=xp, exc=e)
        else:
            log.info("Sem XPaths de editoria; usando homepage como seção única", stage="editorial")

        section_urls = editorial_urls or {config.vehicle.url}

        # ---------------------------------------------------------------------
        # 2) Links de notícia por seção
        # ---------------------------------------------------------------------
        for sec_url in section_urls:
            try:
                sec_root = root if sec_url == config.vehicle.url else _fetch(sec_url, timeout=timeout)
                if sec_root is not root:
                    log.ok("GET 200 (seção)", stage="http-get", url=sec_url)
            except Exception as e:
                log.error("Falha ao carregar seção", stage="listing", url=sec_url, exc=e)
                continue

            found_here = 0

            # Tenta o XPath configurado
            if (config.listing_link_xpath or "").strip():
                try:
                    listing_nodes = sec_root.xpath(config.listing_link_xpath)
                    hrefs = _strings_from_nodes(listing_nodes)
                    for h in hrefs:
                        found_links.add(urljoin(sec_url, h))
                    found_here += len(hrefs)
                    if hrefs:
                        log.ok(f"Links coletados: {len(hrefs)}", stage="listing", url=sec_url, xpath=config.listing_link_xpath)
                    else:
                        log.warn("XPath não retornou links; tentando fallbacks", stage="listing", url=sec_url, xpath=config.listing_link_xpath)
                except Exception as e:
                    log.error("Erro no XPath de listagem; tentando fallbacks", stage="listing", url=sec_url, xpath=config.listing_link_xpath, exc=e)

            # Fallbacks genéricos, se necessário
            if found_here == 0:
                for xp in GENERIC_LISTING_XPATHS:
                    try:
                        nodes = sec_root.xpath(xp)
                        hrefs2 = _strings_from_nodes(nodes)
                        for h in hrefs2:
                            found_links.add(urljoin(sec_url, h))
                        if hrefs2:
                            found_here += len(hrefs2)
                            log.ok(f"Fallback de listagem ok: {len(hrefs2)}", stage="listing", url=sec_url, xpath=xp)
                            break
                    except Exception:
                        continue

        log.info(f"Total de links únicos: {len(found_links)}", stage="listing")

        # ---------------------------------------------------------------------
        # 3) Processamento de artigos (em paralelo)
        # ---------------------------------------------------------------------
        def _first_text(xps: list[str], doc: html.HtmlElement) -> str:
            for xp in xps:
                try:
                    val = _text(doc.xpath(xp))
                    if val:
                        log.ok("XPath de fallback executado", stage="xpath", where="fallback", xpath=xp)
                        return val
                except Exception:
                    continue
            return ""

        def process_article(aurl: str) -> int:
            stage = "article"
            try:
                try:
                    art = _fetch(aurl, timeout=timeout)
                    log.ok("GET 200 (artigo)", stage="http-get", url=aurl)
                except requests.exceptions.HTTPError as e:
                    code = getattr(e.response, "status_code", "?")
                    log.error(f"HTTP {code} no artigo", stage=stage, url=aurl, exc=e)
                    return 0
                except Exception as e:
                    log.error("Falha ao carregar artigo", stage=stage, url=aurl, exc=e)
                    return 0

                # --- Título
                title = ""
                if (config.article_title_xpath or "").strip():
                    try:
                        nodes = art.xpath(config.article_title_xpath)
                        title = _text(nodes)
                        log.ok("XPath executado (título)", stage="xpath", xpath=config.article_title_xpath, nodes=len(nodes))
                    except Exception as e:
                        log.error("Erro de XPath (título)", stage="xpath", xpath=config.article_title_xpath, url=aurl, exc=e)
                if not title:
                    title = _first_text([
                        "//meta[@property='og:title']/@content",
                        "//title",
                        "//*[self::h1 or self::h2][1]"
                    ], art)
                if not title:
                    log.error("Título vazio", stage="article-title", url=aurl)
                    return 0

                # --- Subtítulo
                subtitle = ""
                if (config.article_subtitle_xpath or "").strip():
                    try:
                        subtitle = _text(art.xpath(config.article_subtitle_xpath))
                        log.ok("XPath executado (subtítulo)", stage="xpath", xpath=config.article_subtitle_xpath)
                    except Exception as e:
                        log.error("Erro de XPath (subtítulo)", stage="xpath", xpath=config.article_subtitle_xpath, url=aurl, exc=e)

                # --- Autor
                author = ""
                if (config.article_author_xpath or "").strip():
                    try:
                        author = _text(art.xpath(config.article_author_xpath))
                        log.ok("XPath executado (autor)", stage="xpath", xpath=config.article_author_xpath)
                    except Exception as e:
                        log.error("Erro de XPath (autor)", stage="xpath", xpath=config.article_author_xpath, url=aurl, exc=e)

                # --- Conteúdo
                content = ""
                if (config.article_content_xpath or "").strip():
                    try:
                        nodes = art.xpath(config.article_content_xpath)
                        content = _text(nodes)
                        log.ok("XPath executado (conteúdo)", stage="xpath", xpath=config.article_content_xpath, nodes=len(nodes), chars=len(content))
                    except Exception as e:
                        log.error("Erro de XPath (conteúdo)", stage="xpath", xpath=config.article_content_xpath, url=aurl, exc=e)
                if not content:
                    for xp in GENERIC_CONTENT_XPATHS:
                        try:
                            nodes = art.xpath(xp)
                            content = _text(nodes)
                        except Exception:
                            continue
                        if content:
                            log.ok("Fallback de conteúdo", stage="article-content", xpath=xp, nodes=len(nodes), chars=len(content))
                            break
                if not content:
                    log.error("Conteúdo vazio", stage="article-content", url=aurl)
                    return 0

                # --- Data de publicação
                published_at = None
                if (config.article_date_xpath or "").strip():
                    try:
                        ds = _text(art.xpath(config.article_date_xpath))
                        if ds:
                            published_at = parse_news_datetime(ds)
                            if published_at:
                                log.ok("Data parseada", stage="article-date", value=str(published_at), url=aurl)
                            else:
                                log.warn("Data não parseável (usaremos captured_at)", stage="article-date", raw_date=ds, url=aurl)
                    except Exception as e:
                        log.error("Erro de XPath (data)", stage="xpath", xpath=config.article_date_xpath, url=aurl, exc=e)
                if not published_at:
                    for xp in META_DATE_FALLBACKS:
                        try:
                            val = _text(art.xpath(xp))
                        except Exception:
                            val = ""
                        if val:
                            dt = parse_news_datetime(val)
                            if dt:
                                published_at = dt
                                log.ok("Data parseada (fallback)", stage="article-date-fallback", value=str(dt), xpath=xp, url=aurl)
                                break
                if not published_at:
                    published_at = timezone.now()
                    log.warn("Usando data/hora da captura", stage="article-date-fallback", value=str(published_at), url=aurl)

                # --- Seção (nome dentro do artigo)
                section_obj = None
                if (config.article_section_name_xpath or "").strip():
                    try:
                        sname = _text(art.xpath(config.article_section_name_xpath))
                        if sname:
                            section_obj, _ = Section.objects.get_or_create(
                                vehicle=config.vehicle, name=sname[:150]
                            )
                            log.ok("Seção identificada", stage="article-section-name", section=sname, url=aurl)
                    except Exception as e:
                        log.error("Erro de XPath (seção no artigo)", stage="xpath", xpath=config.article_section_name_xpath, url=aurl, exc=e)

                # --- Persistência
                with transaction.atomic():
                    obj, created = News.objects.get_or_create(
                        vehicle=config.vehicle,
                        url=aurl,
                        defaults=dict(
                            section=section_obj,
                            title=title,
                            subtitle=subtitle,
                            author=author,
                            published_at=published_at,
                            content=content,
                        ),
                    )
                    if created:
                        log.ok("Notícia registrada", stage=stage, article_url=aurl, title=title)
                        return 1
                    else:
                        changed = False
                        if not obj.section and section_obj:
                            obj.section = section_obj; changed = True
                        if not obj.subtitle and subtitle:
                            obj.subtitle = subtitle; changed = True
                        if not obj.author and author:
                            obj.author = author; changed = True
                        if not obj.published_at and published_at:
                            obj.published_at = published_at; changed = True
                        if changed:
                            obj.save()
                            log.ok("Notícia atualizada", stage=stage, article_url=aurl, title=title)
                        else:
                            log.skip("Notícia já existente (sem mudanças)", stage=stage, article_url=aurl)
                        return 0

            except Exception as e:
                # Qualquer falha inesperada no artigo
                log.error("Falha ao processar artigo", stage=stage, url=aurl, exc=e)
                return 0

        if found_links:
            # Limpa e processa (descarta não-http)
            links = [u for u in found_links if isinstance(u, str) and u.startswith("http")]
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
                for added in ex.map(process_article, links):
                    try:
                        new_count += int(added)
                    except Exception:
                        pass

        # ---------------------------------------------------------------------
        # Finalização OK
        # ---------------------------------------------------------------------
        log.info("Importação concluída", stage="end", found=len(found_links), new=new_count)

        job.status = ImportStatus.DONE
        job.finished_at = timezone.now()
        job.found_count = len(found_links)
        job.new_count = new_count
        job.log = json.dumps({"events": log.events}, ensure_ascii=False)
        job.save(update_fields=["status", "finished_at", "found_count", "new_count", "log"])

        config.status = ImportStatus.DONE
        config.save(update_fields=["status"])

        return job

    except Exception as e:
        # ---------------------------------------------------------------------
        # Falha geral
        # ---------------------------------------------------------------------
        log.error(f"Falha fatal: {type(e).__name__}: {e}", stage="fatal", exc=e)

        job.status = ImportStatus.FAILED
        job.finished_at = timezone.now()
        job.log = json.dumps({"events": log.events}, ensure_ascii=False)
        job.save(update_fields=["status", "finished_at", "log"])

        config.status = ImportStatus.FAILED
        config.save(update_fields=["status"])

        return job
