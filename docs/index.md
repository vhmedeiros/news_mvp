# News MVP — Documentação de Código

> Projeto **Django 5** para captura de notícias via **XPath** (requests + lxml), com **CRUD** de veículos, **configurações de importação**, **jobs com log estruturado**, listagem/detalhe de notícias e **dashboard** com **Chart.js**.

---

## Sumário

* [Configuração do projeto](#configuração-do-projeto)

  * [`app/settings.py`](#appsettingspy)
  * [`app/urls.py`](#appurlspy)
* [Domínio & dados](#domínio--dados)

  * [`veiculos/models.py` (Vehicle, Section)](#veiculosmodelspy-vehicle-section)
  * [`noticias/models.py` (News)](#noticiasmodelspy-news)
  * [`importacoes/models.py` (ImportConfig, ImportJob, ImportStatus)](#importacoesmodelspy-importconfig-importjob-importstatus)
* [Scraper & agendamento](#scraper--agendamento)

  * [`importacoes/services.py` (scraper)](#importacoesservicespy-scraper)
  * [`importacoes/scheduler.py` (opcional)](#importacoesschedulerpy-opcional)
* [Camada web (views)](#camada-web-views)

  * [`importacoes/views.py`](#importacoesviewspy)
  * [`noticias/views.py`](#noticiasviewspy)
  * [`veiculos/views.py`](#veiculosviewspy)
* [Formulários](#formulários)

  * [`importacoes/forms.py` (ImportConfigForm)](#importacoesformspy-importconfigform)
* [Templates — layout & componentes](#templates--layout--componentes)

  * [`app/templates/base.html`](#apptemplatesbasehtml)
  * Componentes: [`components/page_header.html`](#componentspage_headerhtml), [`components/paginator.html`](#componentspaginatorhtml), [`components/sidebar.html`](#componentssidebarhtml), [`components/header.html`](#componentsheaderhtml), [`components/footer.html`](#componentsfooterhtml)
* [Templates — Dashboard](#templates--dashboard)

  * [`app/templates/dashboard/index.html`](#apptemplatesdashboardindexhtml)
* [Templates — Importações](#templates--importações)

  * Partials: [`imports/partials/_event_line.html`](#importspartials_event_linehtml), [`imports/partials/_event_line_inner.html`](#importspartials_event_line_innerhtml)
  * Páginas: [`imports/import_list.html`](#importsimport_listhtml), [`imports/import_detail.html`](#importsimport_detailhtml), [`imports/import_form.html`](#importsimport_formhtml), [`imports/job_detail.html`](#importsjob_detailhtml)
* [Templates — Notícias](#templates--notícias)

  * [`news/news_list.html`](#newsnews_listhtml), [`news/news_detail.html`](#newsnews_detailhtml)
* [Templates — Veículos](#templates--veículos)

  * [`vehicles/vehicle_list.html`](#vehiclesvehicle_listhtml), [`vehicles/vehicle_form.html`](#vehiclesvehicle_formhtml), [`vehicles/vehicle_detail.html`](#vehiclesvehicle_detailhtml), [`vehicles/vehicle_confirm_delete.html`](#vehiclesvehicle_confirm_deletehtml)
* [Modelo de dados (ERD)](#modelo-de-dados-erd)
* [Como rodar (dev)](#como-rodar-dev)
* [Boas práticas de XPath](#boas-práticas-de-xpath)
* [Pontos de atenção & extensões](#pontos-de-atenção--extensões)

---

## Configuração do projeto

### `app/settings.py`

* **INSTALLED\_APPS**: `veiculos`, `importacoes`, `noticias`, `dashboard` (além dos apps Django).
* **Templates**: diretório base em `app/templates` (via `DIRS`).
* **Idioma/Fuso**: `pt-br` e `America/Sao_Paulo`.
* **Banco**: SQLite (`db.sqlite3`) por padrão — fácil para dev; pode trocar para PostgreSQL.
* **ALLOWED\_HOSTS**: ajuste conforme ambiente (produção vs dev).

**Boas práticas para produção**

* Defina `DEBUG=False`, configure `ALLOWED_HOSTS`.
* Armazene `SECRET_KEY` e credenciais via variáveis de ambiente.
* Ative cabeçalhos de segurança (`SECURE_*`, `CSRF_*`) e HTTPS.

### `app/urls.py`

* `/admin/` — admin do Django.
* `/vehicles/` — rotas do app **veiculos**.
* `/imports/` — rotas do app **importacoes**.
* `/news/` — rotas do app **noticias**.
* `/dashboard/` — rotas do **dashboard**.
* `/` → redireciona para **`/news/`**.

---

## Domínio & dados

### `veiculos/models.py` (Vehicle, Section)

**`Vehicle`**

* Campos: `name`, `media_type` (choices), `status` (choices), `country`, `state`, `city`, `url`, `notes`, `created_at`, `updated_at`.
* `location_display()` monta string amigável (ex.: “Cuiabá, MT, Brasil”).
* **Choices**:

  * `media_type`: `site`, `blog`, `magazine`, `television`, `radio`, `podcast`, `videocast`.
  * `status`: `active`, `inactive`.

**`Section`**

* Campos: `vehicle` (FK) e `name`.
* `unique_together (vehicle, name)` evita duplicidade de seção por veículo.

> O scraper pode criar/associar `Section` automaticamente quando você fornece XPath do **nome da editoria dentro do artigo**.

### `noticias/models.py` (News)

**`News`**

* Campos: `vehicle` (FK), `section` (FK opcional), `url` (única por veículo), `title`, `subtitle` (opcional), `author` (opcional), `published_at` (opcional), `captured_at` (auto), `content` (texto longo).
* `unique_together (vehicle, url)` evita duplicatas do mesmo veículo.
* Índices em `published_at` e `title`.
* Ordenação padrão: `-published_at`, `-captured_at`.

### `importacoes/models.py` (ImportConfig, ImportJob, ImportStatus)

**`ImportStatus`**: `idle`, `running`, `failed`, `done`.

**`ImportConfig`** (configuração por veículo)

* Campos principais:

  * `vehicle`, `name` (único por veículo).
  * `editorial_xpaths` (**opcional**, multi-linha; um XPath por linha que **retorna links** de seções).
  * `listing_link_xpath` (links de notícia **na página da seção**).
  * Dentro do artigo:

    * `article_title_xpath` (**recomendado**),
    * `article_subtitle_xpath` (opcional),
    * `article_author_xpath` (opcional),
    * `article_date_xpath` (opcional),
    * `article_section_name_xpath` (opcional),
    * `article_content_xpath` (**importante**).
  * Agendamento: `interval_minutes` (padrão **20**), `enabled` (bool), `last_run_at`, `status`.
* Ordenação: por `vehicle__name`, `name`.

**`ImportJob`** (execução)

* Campos: `config` (FK), `started_at`, `finished_at`, `status`, `found_count`, `new_count`, `log` (JSON/texto).
* Método: `mark_done(found, new)`.

---

## Scraper & agendamento

### `importacoes/services.py` (scraper)

**Fluxo (resumo do `run_import(config_id)`):**

1. Cria `ImportJob(status=RUNNING)`, marca `ImportConfig.status=RUNNING` e atualiza `last_run_at`.
2. **Homepage**: `GET` com `DEFAULT_HEADERS` (User-Agent, Accept).
3. **Editorias (opcional)**:

   * Lê `editorial_xpaths` (linhas não vazias).
   * Para cada XPath, retorna `@href` ou descobre `<a>` internos; normaliza com `urljoin`.
   * Se vazio, usa a **homepage** como “seção única”.
4. **Listagem por seção**:

   * Aplica `listing_link_xpath`; se não vier nada, usa fallbacks genéricos:

     * `//article//a/@href`, `//h2//a/@href`, `//h3//a/@href`,
     * ou `<a>` cujo `href` sugira notícia (`/noticia`, `/news`, `/materia`).
   * Acumula links únicos em `found_links`.
5. **Artigos (paralelo – `ThreadPoolExecutor`)**:

   * **Título**: XPath configurado → fallbacks (`og:title`, `<title>`, primeiro `h1/h2`).
   * **Subtítulo/Autor**: se definidos, extrai.
   * **Conteúdo**: XPath configurado → fallbacks (`//article//p`, `//main//p`, classes com `content/article`).
   * **Data**: XPath configurado → fallbacks (`meta[article:published_time]`, `<time datetime>`, `.date`) → se falhar, usa **captura** (agora).
   * **Seção no artigo**: se presente, cria/associa `Section`.
   * **Persistência**:

     * `get_or_create(vehicle, url)`; se **novo**, conta como “new”.
     * Se já existe, atualiza **apenas campos vazios** (subtitle/author/published\_at/section) e salva se houve mudança; senão faz “skip”.
6. **Finalização**:

   * Salva `found_count`, `new_count`, `status=DONE`, e `log={"events":[...]}` no `Job`, além de `status=DONE` na `ImportConfig`.
   * Em exceções gerais, marca `status=FAILED` e grava evento `fatal` no log.

**Parser de data PT-BR (`parse_news_datetime`)**

* Remove caudas (ex.: “Atualizado: …”, partes após `|`/travessão).
* Ignora dia da semana; normaliza `11h30`→`11:30`, `11h`→`11:00`.
* Converte meses PT→EN e tenta `dateutil.parse(dayfirst=True)`.
* Fallback para `dd/mm/aaaa HH:MM(:SS)?`.
* Ajusta para timezone-aware com TZ do Django se vier “naive”.

**Logs estruturados (`JsonLogger`)**

* Evento: `{ level, msg, stage, url, xpath, ts, ...extras }`.
* Níveis: `info`, `ok`, `warn`, `skip`, `error`.
* Em `error` com exceção: inclui `exc_type` e `trace` curto.
* `job.log` recebe `{"events":[...]}`.
* **Dica:** a UI de Job aceita `?level=errors` para listar **somente erros**.

### `importacoes/scheduler.py` (opcional)

* `_due_configs()`: pega configs **habilitadas** cujo `last_run_at` venceu (`interval_minutes`) ou nunca executadas; ignora `status=RUNNING`.
* `_loop()`: a cada \~60s, dispara `run_import` em **thread** por config “devida”.
* `start_scheduler()`: inicia a thread **uma única vez** (flag interna).

> **Importante:** o scheduler **só executa** se você chamar `start_scheduler()` (ex.: em `apps.py::ready()`). Em dev, atenção ao autoreload do `runserver` (evitar iniciar 2x).

---

## Camada web (views)

### `importacoes/views.py`

* **Lista de importações**: tabela com veículo, nome, status (badges), intervalo, última execução e ações (ver/editar).
  *A interface possui o link **“Executar todas”** na Sidebar.*
* **Detalhe de importação**: resume status/intervalo/última execução, mostra **execuções (Jobs)** e atalho para o log mais recente.
* **Formulário**: usa `ImportConfigForm` (com placeholders e ajuda para XPaths).
* **Job detail**:

  * Lê `job.log` e **parseia** formatos tolerantes (dict, list, JSONL, JSON concatenado; fallback de texto).
  * **Agrupa por artigo** (quando a URL do artigo aparece no evento).
  * Contadores por **nível** e por **etapa**.
  * Suporta `?level=errors` (somente erros) e `?level=all` (todos).
  * Usa partials `_event_line.html` e `_event_line_inner.html` para renderização consistente.

> **Execução manual**
>
> * **Executar todas**: dispara cada `ImportConfig` habilitada em thread.
> * *(Se existir na sua UI)* **Executar agora** em uma importação específica.

### `noticias/views.py`

* **Listagem**:

  * Filtros: `?q=...` (título `icontains`), `?vehicle=<id>`.
  * `select_related("vehicle", "section")`.
  * Paginação (20 p/ página).
* **Detalhe**:

  * Mostra campos principais + **link para o original**.
  * Conteúdo com `|linebreaks`.

### `veiculos/views.py`

* **Listagem**:

  * Filtros: `q` (nome), `media_type`, `status`.
  * Mostra **chips** de filtros ativos e total “Exibindo X de Y”.
* **Detalhe**:

  * Card com dados do veículo; **badges** de status.
  * Ações: Voltar, Editar, Abrir site, **Nova importação** (do veículo).
  * Cards de **contadores** (se o contexto fornecer): `sections`, `imports`, `news`.
  * Listas de **importações** e **notícias** recentes do veículo (quando presentes no contexto).
* **CRUD**: create/update/delete (com confirmação).

---

## Formulários

### `importacoes/forms.py` (ImportConfigForm)

* `ModelForm` de `ImportConfig`.
* Widgets `Textarea` com **placeholders** úteis:

  * `editorial_xpaths` (5 linhas, um XPath por linha).
  * `listing_link_xpath` (2 linhas).
  * `article_*_xpath` (2–3 linhas conforme o campo).
* Campos básicos (`vehicle`, `name`, `interval_minutes`, `enabled`) estilizados e com ajuda textual clara.

---

## Templates — layout & componentes

### `app/templates/base.html`

* Estrutura **Bootstrap 5** via CDN.
* Layout **2 colunas**:

  * **Sidebar** com navegação e ações (Nova importação, Executar todas).
  * **Main** com: `components/page_header.html`, mensagens (`django.contrib.messages`) e bloco `{% block content %}`.
* Inclui `bootstrap.bundle.min.js` no final.

### `components/page_header.html`

* Cabeçalho reaproveitável:

  * **Título**: bloco `{% block header %}`.
  * **Subtítulo**: variável `subtitle` ou bloco `subheader`.
  * **Ações**: bloco `header_actions`.
  * **Breadcrumbs**: bloco `breadcrumbs`.
* Linha separadora `<hr>`.

### `components/paginator.html`

* Controles: **Primeira/Anterior/Próxima/Última**.
* Janela dinâmica de páginas com **reticências**.
* **Preserva** parâmetros via templatetag `urlparams`.
* Mostra **“Página X de Y”**.

> Requer `{% load urltools %}` no topo do template e que a view passe `is_paginated`/`page_obj`.

### `components/sidebar.html`

* Itens: **Importações**, **Veículos**, **Notícias**, **Dashboard** (marca ativo).
* **Ações rápidas** na seção Importações:

  * **Nova importação**
  * **Executar todas** (executa todas as importações habilitadas)

### `components/header.html` / `components/footer.html`

* **Header** simples com branding “News MVP”.
* **Footer** discreto; bom lugar para versão/créditos.

---

## Templates — Dashboard

### `app/templates/dashboard/index.html`

* **Filtros**: granularidade (**Dia/Mês/Ano**), intervalo (`from`/`to`).
* **Cards**: Total no período, Total geral, Total de veículos.
* **Gráficos (Chart.js)**:

  * **Série temporal** (barras) com bucketização de datas (tooltip mostra intervalos agregados).
  * **Top veículos** (barras horizontais, top 10).
  * **Por tipo de veículo** (barras).
* Dados passados ao JS via `json_script`.

---

## Templates — Importações

### `imports/partials/_event_line.html`

* Linha de **evento** (log) com:

  * **Badge** por nível (`error`/`warn`/`ok`/default),
  * `stage` (em `<code>`), `ts`,
  * `msg` + **XPath** + **URL** (quando presentes),
  * Detalhes (`extra`/`trace`) em `<details>` (colapsável).

### `imports/partials/_event_line_inner.html`

* Versão **compacta** para acordeões de artigo (mesma semântica de cores/metadados).

### `imports/import_list.html`

* Tabela com: **Veículo**, **Nome**, **Status** (badges), **Intervalo**, **Última execução**, **Ações** (Editar/Ver).
* Integra com `components/paginator.html`.

### `imports/import_detail.html`

* **Resumo**: veículo, status, intervalo, última execução, “habilitada”.
* **Ações**: *(se houver na sua UI)* **Executar agora**, **Editar**, **Voltar**.
* **XPaths configurados** (acordeão).
* **Tabela de execuções (Jobs)** com link **Ver** para cada log.
* **Último log** (texto/JSON) mostrado em `<pre>` e atalho “Ver log completo”.

### `imports/import_form.html`

* Form em **cards**:

  * **Configuração básica**: Veículo, Nome, Intervalo (min), Habilitada.
  * **Navegação**: XPaths de **editorias** (um por linha; **opcional**) e **links** de notícia (listagem).
  * **Artigo**: Título\*, Subtítulo, Autor, Data, Nome da editoria (no artigo), Conteúdo\*.
* **Placeholders** e ajuda textual (explica fallbacks).
* Barra de ações **grudenta** (Cancelar/Salvar).

### `imports/job_detail.html`

* **Resumo**: Status, Início, Fim, Encontradas, Novas.
* Quando o log é estruturado (JSON):

  * **Contadores** por nível (`info`, `ok`, `warn`, `skip`, `error`),
  * **Contagem por etapa**,
  * **Geral** (eventos sem artigo) e **Acordeão por artigo** (com URL e, quando houver, título).
* **Filtro de erros**: `?level=errors` mostra apenas erros mantendo o **visual bonito** via partials.
* Botão **Voltar** para o detalhe da importação.

---

## Templates — Notícias

### `news/news_list.html`

* **Busca** (`?q=`) por título; coluna para **Veículo** e **Seção**.
* Link externo ↗ para abrir a notícia original.
* Paginação via `components/paginator.html`.

### `news/news_detail.html`

* Mostra: título, subtítulo, veículo, seção, autor, publicado, capturado, e botão **“Abrir original”**.
* **Conteúdo** renderizado com `|linebreaks` em card.

---

## Templates — Veículos

### `vehicles/vehicle_list.html`

* **Filtros**: Busca por nome (com botão “limpar”), **Tipo** e **Status** (choices).
* Mostra “**Exibindo X de Y**” + **chips de filtros**.
* Tabela: **Nome**, **Tipo**, **Status** (badges), **Localização**, **URL**, **Ações**.
* Botão **“Novo veículo”**.
* Inclui `components/paginator.html`.

### `vehicles/vehicle_form.html`

* Seções do form:

  * **Identificação**: Nome, URL (com auto-prefixo `https://` se faltar).
  * **Classificação**: Tipo, Status.
  * **Localização**: País, Estado, Cidade.
  * **Observações**: textarea amplo.
* Barra de ações **grudenta** (Cancelar/Salvar).
* JS mínimo para completar `https://` no `blur` do campo URL.

### `vehicles/vehicle_detail.html`

* Ações: **Voltar**, **Editar**, **Abrir site**, **Nova importação** para o veículo.
* Card com dados gerais; badges de `status`.
* “Criado/Atualizado”: mostrados com `timesince`.
* Se o contexto trouxer, renderiza **cards-resumo** (editorias/importações/notícias) e listas de **importações/notícias recentes**.

### `vehicles/vehicle_confirm_delete.html`

* Alerta de exclusão permanente + contadores de relacionados (se fornecidos).
* Mostra dados do veículo a excluir.
* Form `POST` com confirmação; botão **Cancelar**.

---

## Modelo de dados (ERD)

```mermaid
erDiagram
  VEHICLE ||--o{ SECTION : has
  VEHICLE ||--o{ IMPORTCONFIG : has
  VEHICLE ||--o{ NEWS : has
  IMPORTCONFIG ||--o{ IMPORTJOB : has
  SECTION ||--o{ NEWS : tags

  VEHICLE {
    bigserial id PK
    varchar name
    varchar media_type
    varchar status
    varchar country
    varchar state
    varchar city
    varchar url
    text    notes
    timestamptz created_at
    timestamptz updated_at
  }

  SECTION {
    bigserial id PK
    FK vehicle_id -> VEHICLE.id
    varchar name
    UNIQUE (vehicle_id, name)
  }

  NEWS {
    bigserial id PK
    FK vehicle_id -> VEHICLE.id
    FK section_id -> SECTION.id NULL
    varchar url
    text    title
    text    subtitle NULL
    text    author NULL
    timestamptz published_at NULL
    timestamptz captured_at
    text    content
    UNIQUE (vehicle_id, url)
  }

  IMPORTCONFIG {
    bigserial id PK
    FK vehicle_id -> VEHICLE.id
    varchar name
    text editorial_xpaths NULL
    text listing_link_xpath
    text article_title_xpath
    text article_subtitle_xpath NULL
    text article_author_xpath NULL
    text article_date_xpath NULL
    text article_section_name_xpath NULL
    text article_content_xpath
    int  interval_minutes DEFAULT 20
    bool enabled DEFAULT true
    timestamptz last_run_at NULL
    varchar status
    UNIQUE (vehicle_id, name)
  }

  IMPORTJOB {
    bigserial id PK
    FK config_id -> IMPORTCONFIG.id
    timestamptz started_at
    timestamptz finished_at NULL
    varchar status
    int found_count DEFAULT 0
    int new_count DEFAULT 0
    text log
  }
```

---

## Como rodar (dev)

```bash
# 1) instalar dependências
pip install -r requirements.txt

# 2) migrar
python manage.py migrate

# 3) (opcional) criar superusuário
python manage.py createsuperuser

# 4) rodar servidor
python manage.py runserver 0.0.0.0:8889
# abra http://localhost:8889/  (redireciona para /news/)
```

* **Executar importações**: use **Importações → Executar todas** (na Sidebar).
  *(Se a sua UI tiver o botão “Executar agora” no detalhe da importação, ele dispara apenas aquela configuração.)*
* **Agendamento automático** (opcional): chame `start_scheduler()` (ex.: em `apps.py::ready()`) para reexecutar configs conforme `interval_minutes`.

---

## Boas práticas de XPath

* **Editorias** (opcional): cada linha deve retornar um **link** (`@href`) ou elementos com `<a>` internos.
* **Listagem**: XPath que **retorna links de notícia** na página da seção. Existem fallbacks genéricos, mas variam por site.
* **Notícia**:

  * Título: `//h1` (fallbacks para `og:title`, `<title>`, `<h2>`).
  * Conteúdo: **parágrafos** (`//article//p`, `//main//p`, classes `content/article`).
  * Data: prefira `<time datetime>` ou meta `article:published_time`. O parser PT-BR é tolerante; se não parsear, usa a **data/hora da captura**.

---

## Pontos de atenção & extensões

* **Scheduler**: precisa ser explicitamente habilitado; em dev, cuidado com autoreload do `runserver` (garanta instância única).
* **Performance**: para alto volume, migrar para **PostgreSQL** e usar **fila** (Celery/Redis) em vez de threads.
* **Páginas dinâmicas**: para sites pesados em JS, considerar **Selenium/Playwright**.
* **Rede/anti-bloqueio**: para rotação de **IP/proxy/VPN**, integrar provedores externos.
* **Logs**: `ImportJob.log` armazena JSON; a UI de Job permite **somente erros** via `?level=errors`.
