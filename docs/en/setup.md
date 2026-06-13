# Setup & Installation Guide

This guide walks through getting Janus Platform running locally on Windows
(PowerShell), with notes for macOS/Linux where they differ.

## Prerequisites

- **Python 3.12+**
- **Docker Desktop** (for Neo4j)
- **Tesseract OCR** (for scanned PDF support in Document Brain) — on Windows,
  install from https://github.com/UB-Mannheim/tesseract/wiki and make sure
  `tesseract.exe` is on your `PATH`. On Linux: `apt-get install tesseract-ocr tesseract-ocr-rus`.
- A **Yandex Cloud** account with a folder ID and an API key (for the LLM).

## 1. Clone and create a virtual environment

```powershell
git clone https://github.com/Artem-Kornilov-pro/janus-platform.git
cd janus-platform
python -m venv .venv
.venv\Scripts\Activate.ps1
```

## 2. Install dependencies

```powershell
pip install -r requirements.txt
```

This includes the core libraries, PyQt6 (frontend), and dev/test tools
(`pytest`, `pytest-asyncio`). Alternatively, with `pyproject.toml`:

```powershell
pip install -e ".[frontend,dev]"
```

## 3. Configure environment variables

Copy the example file and fill in your credentials:

```powershell
copy .env.example .env
```

Edit `.env`:

```dotenv
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=janustest123

YANDEX_CLOUD_FOLDER=<your folder id>
YANDEX_CLOUD_API_KEY=<your api key>
YANDEX_CLOUD_MODEL=deepseek-v4-flash/latest

MCP_TRANSPORT=sse
MCP_HOST=127.0.0.1
MCP_PORT=8000

MCP_SERVER_URL=http://localhost:8000/sse
```

> `.env` is gitignored — never commit real credentials.

The Python processes below read `.env` via your shell environment. If you
use PowerShell, load it with:

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim())
    }
}
```

(or use a tool like `direnv` / `python-dotenv` if you prefer.)

## 4. Start Neo4j

```powershell
docker compose up -d
```

This starts only the `neo4j` service (container `janus-neo4j`), exposing:
- `7474` — Neo4j Browser (http://localhost:7474)
- `7687` — Bolt protocol

Wait until `docker ps` shows it as `healthy`.

## 5. Start the MCP Fabric server

Run it **locally** (not in Docker), so it can read the same filesystem paths
the frontend's folder picker uses:

```powershell
python -m core.mcp_fabric.server
```

You should see `Uvicorn running on http://127.0.0.1:8000`. Leave this
running in its own terminal.

> An optional containerized variant exists: `docker compose --profile docker up -d`.
> Use it only if you don't need the "ingest folder" feature, or adapt volume
> mounts to your document locations.

## 6. Run the frontend

In a new terminal (with the same `.env` loaded):

```powershell
cd frontend
python app.py
```

The PyQt6 window opens with four tabs: **Чат**, **Документы**, **Сущности**,
**Learning Brain**.

## 7. (Optional) Ingest documents from the command line

```powershell
python janus_ingest.py --folder fixtures/ingestion --recursive
python janus_ingest.py --status <job_id>
```

## 8. (Optional) Review/label extractions interactively

```powershell
python feedback_cli.py
```

## Running tests

```powershell
pytest -q
```

All 25+ tests should pass without Docker/LLM access (they use fixtures and
mocks); a few `demo/*.py` scripts under `demo/` are live smoke tests that
require Neo4j + Yandex Cloud credentials.

## Using the Makefile

If you have `make` available (Git Bash, WSL, macOS, Linux), see the
[Makefile](../../Makefile) for shortcuts:

```bash
make install      # pip install -r requirements.txt
make up           # docker compose up -d (Neo4j)
make down         # docker compose down
make server       # run the MCP Fabric server locally
make frontend     # run the PyQt6 frontend
make test         # run pytest
make ingest FOLDER=fixtures/ingestion  # ingest a folder via CLI
```

## Troubleshooting

- **`Couldn't connect to localhost:7687`** — Neo4j container isn't running; `docker start janus-neo4j` or `docker compose up -d`.
- **`Could not reach MCP server at http://localhost:8000/sse`** — the MCP server isn't running; start it with `python -m core.mcp_fabric.server`.
- **`Error executing tool ingest_folder: ... Couldn't connect to ...:7687`** — same as above, Neo4j is down.
- **`'OpenAI' object has no attribute 'responses'` / `Client.__init__() got an unexpected keyword argument 'proxies'`** — your `openai`/`httpx` versions are out of sync; reinstall with `pip install -r requirements.txt`.
- **Folder ingestion via the frontend does nothing / fails for a Docker-based MCP server** — run the MCP server locally, not in Docker (see step 5).
