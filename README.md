# News MVP — Scraper de veículos de mídia (Django)

> MVP educacional para **coletar notícias via XPath** de sites/blogs, armazenar em **SQLite/PostgreSQL**, exibir com **Django + Bootstrap**, e acompanhar tudo em um **Dashboard** com **Chart.js**. Possui **logs estruturados por execução**.

---

## Sumário

* [Arquitetura](#arquitetura)
* [Tecnologias](#tecnologias)
* [Pré-requisitos](#pré-requisitos)
* [Instalação & Setup](#instalação--setup)
* [Como rodar](#como-rodar)
* [Fluxo de uso](#fluxo-de-uso)
* [Dashboard](#dashboard)
* [Logs de importação](#logs-de-importação)
* [XPath — dicas rápidas](#xpath--dicas-rápidas)
* [Banco de dados: SQLite vs PostgreSQL](#banco-de-dados-sqlite-vs-postgresql)
* [Problemas comuns](#problemas-comuns)
* [Roadmap](#roadmap)
* [Aviso legal](#aviso-legal)
* [Licença](#licença)

---

## Arquitetura

**Apps Django**

* `veiculos/` — CRUD de veículos (nome, tipo, status, localização, URL, notas).
* `importacoes/` — Configurações de importação (XPaths, *intervalo* — faz a reexecução automática quando o intervalo é vencido —, habilitada), execução manual via **“Executar todas”** e **logs estruturados** (JSON).
* `noticias/` — Banco de notícias (veículo, seção, URL, título, subtítulo, autor, publicado em, capturado em, conteúdo).
* `dashboard/` — Estatísticas de importações/notícias com **Chart.js** (filtros por dia, mês, ano).

**Templates**

* `app/templates/` com **layout base** (`base.html`), **sidebar**, **header**, **footer**, **paginator** e telas de CRUD.
* Logs de execução com acordeão por artigo e **parciais** (`imports/partials/_event_line*.html`) para visual limpo.

**Serviço de scraping**

* Implementado em `importacoes/services.py` usando **requests + lxml (XPath)**.
* Parser de datas **PT-BR robusto** (normalização + `python-dateutil`) com fallbacks para meta tags.
* Fallbacks de **listagem** e **conteúdo** quando o XPath não retorna nós (ex.: `//article//a/@href`, `//article//p`).
* **Logs estruturados** por etapa (`editorial`, `listing`, `article-…`) com níveis (`info`, `ok`, `warn`, `skip`, `error`).

---

## Tecnologias

* **Django 5**
* **Requests** + **lxml** (XPath)
* **python-dateutil**
* **Bootstrap 5**
* **Chart.js**
* Banco: **SQLite** (desenvolvimento) / **PostgreSQL** (opcional para produção)

> Dependências em `requirements.txt`.

---

## Pré-requisitos

* Python **3.11+**
* `git`

---

## Instalação & Setup

```bash
# clone
git clone https://github.com/<seu-usuario>/news_mvp.git
cd news_mvp

# ambiente virtual
python -m venv venv
# Windows (PowerShell):
venv\Scripts\Activate
# Linux/macOS:
# source venv/bin/activate

# dependências
pip install -r requirements.txt

# migrações
python manage.py migrate

# (opcional) superusuário
python manage.py createsuperuser
```

> **Dados de exemplo (opcional):** se houver um `data.json`, você pode carregar com:
>
> ```bash
> python manage.py loaddata data.json
> ```

---

## Como rodar

### Servidor web (desenvolvimento)

```bash
python manage.py runserver 0.0.0.0:8889
```

Acesse: `http://localhost:8889/` ou `http://IP_DA_MAQUINA:8889/` na rede local.

---

## Fluxo de uso

1. **Veículos**
   Sidebar → **Veículos** → **Novo Veículo**.
   Preencha **nome**, **tipo**, **status**, **URL**, localização, notas.

2. **Importações**
   Sidebar → **Importações** → **Nova importação**.
   Selecione o veículo, opcionalmente defina um **intervalo (min)** e **habilitada**, e informe os **XPaths**:

   * **Editorias** (um por linha, **opcional**). Se vazio, usa a **homepage** do veículo como seção única.
   * **Listagem** (XPath que retorna **links** de notícias na página da seção).
   * **Notícia**: título (obrigatório), subtítulo (opcional), autor (opcional), data (opcional), seção (opcional), conteúdo (obrigatório).

3. **Executar**
   Na listagem de importações, use **“Executar todas”** para rodar todas as importações configuradas no momento que quiser ou apenas espere o intervalo vencer para reexecutar automaticamente.

4. **Notícias**
   Sidebar → **Notícias** (listagem com busca).
   Clique no título para ver o **detalhe** (inclui link para a notícia original).

5. **Dashboard**
   Sidebar → **Dashboard**.
   Selecione **dia/mês/ano** e veja **barras** (e/ou pizza) por veículo, por tipo etc.

---

## Dashboard

* **Chart.js** via CDN.
* Filtros de período na própria página (dia/mês/ano).
* Gráficos de **barras** (e pizza quando aplicável):

  * Top veículos por quantidade de notícias.
  * Distribuição por **tipo** de veículo (site, blog, rádio, TV, etc.).
* Agregações no banco para evitar peso no frontend.

> Em volumes maiores, considere **PostgreSQL** e índices.

---

## Logs de importação

Cada execução (**Job**) guarda eventos (JSON):

* **nível**: `info`, `ok`, `warn`, `skip`, `error`
* **etapa**: `editorial`, `listing`, `article-title`, `article-content`, `article-date` etc.
* **contexto**: `url`, `xpath`, `ts` e, em erros Python, `exc_type` + `trace` curto.

Na tela do **Job**:

* Resumo: status, início/fim, links encontrados, notícias novas.
* **Acordeão por artigo** com a trilha de eventos.
* Opção para exibir **somente erros**.

---

## XPath — dicas rápidas

* **Editorias** (opcional): XPaths que **retornem `@href`** (um por linha).
  Ex.: `//nav//a/@href` ou containers com `<a>` interno.
* **Listagem**: XPath que retorna **links de matéria** na página de seção.
  Ex.: `//article//a/@href`, `//h2//a/@href`.
* **Notícia**:

  * Título: `//h1` (fallbacks para `og:title` e `<title>`).
  * Data: prefira `<time datetime>` ou meta `article:published_time`; há parser PT-BR tolerante.
  * Conteúdo: parágrafos em `//article//p` (há fallbacks).
* Campos **opcionais** podem ficar vazios (subtítulo, autor, seção, data).

---

## Banco de dados: SQLite vs PostgreSQL

* **SQLite**: excelente para **desenvolvimento e demo** (simples, zero-config).
* **PostgreSQL**: indicado para produção / importações simultâneas / buscas e relatórios.

### Migração para PostgreSQL (resumo)

1. Instale PostgreSQL e crie DB/usuário.
2. Ajuste `DATABASES` no `settings.py`:

   ```python
   DATABASES = {
     "default": {
       "ENGINE": "django.db.backends.postgresql",
       "NAME": "news_mvp",
       "USER": "news_mvp",
       "PASSWORD": "SUA_SENHA",
       "HOST": "localhost",
       "PORT": "5432",
     }
   }
   ```
3. Instale driver:

   ```bash
   pip install "psycopg[binary]"
   ```
4. Migre e (se quiser) carregue dados exportados:

   ```bash
   python manage.py migrate
   python manage.py loaddata data.json
   ```

---

## Problemas comuns

* **Nada é capturado**

  * Verifique **XPaths** e rode **“Executar todas”**; veja o **Job log**.
  * Confirme se a importação está **habilitada** (se sua interface oferece esse controle).

* **Erros de data**

  * O parser aceita várias variações em PT-BR (com/sem dia da semana, `11h30`, `11h:30`, etc.).
  * Se não houver data parseável, usa-se a **data/hora da captura**.

* **Listagem vazia**

  * Ajuste o XPath de listagem para apontar **links de matéria**.
  * Existem fallbacks genéricos (ex.: `//article//a/@href`), mas sites variam bastante.

* **Desempenho**

  * Reduza a quantidade de veículos/URLs por teste.
  * Para muito volume, use **PostgreSQL** + índices.

---

## Roadmap

* [ ] Suporte a **Selenium/Playwright** para páginas dinâmicas
* [ ] **Auto-login** em veículos com paywall simples; integração com **reCAPTCHA** (serviço externo)
* [ ] **Rotação de IP / Proxy / VPN** (pool configurável)
* [ ] **Tarefas assíncronas** (Celery + Redis) e fila de reprocessamento
* [ ] **Docker/Compose** (web + worker + db + redis)
* [ ] Busca full-text e filtros avançados
* [ ] Alertas (e-mail/Telegram) em falhas de importação

---

## Aviso legal

Projeto **educacional**. Antes de coletar conteúdo de um site:

* Respeite **robots.txt**, **Termos de Uso** e **copyright**.
* Evite sobrecarga (respeite intervalos e limites).
* Só colete o que você tem **direito** de processar/armazenar.

---

