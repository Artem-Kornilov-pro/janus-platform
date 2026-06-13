# Frontend (PyQt6 Desktop)

**Path**: `frontend/`

A desktop GUI built with **PyQt6** that connects to the MCP Fabric server
over SSE and exposes its tools through four tabs.

## Files

- `app.py` — entry point: creates `QApplication`, shows `MainWindow`, runs the event loop.
- `main_window.py` — `MainWindow` (`QMainWindow`): owns a single `AsyncRunner` instance and a `QTabWidget` with the four pages below.
- `async_runner.py` — `AsyncRunner`: bridges async MCP calls to Qt.
  - Runs a dedicated background `asyncio` event loop on a `QThread`.
  - `submit(coro_factory)` schedules a coroutine on that loop from a short-lived helper thread (`asyncio.run_coroutine_threadsafe(...).result()`), then emits the Qt signal `finished(call_id, result, error)` — Qt automatically delivers this signal on the **main thread**, so UI code never touches widgets from a background thread.
  - Each page generates a `call_id`, calls `submit(...)`, and filters `finished` events by that id.
- `mcp_client.py` — thin async wrapper over the `mcp` SDK:
  - `call_tool(name, arguments)` opens an `sse_client(MCP_SERVER_URL)` connection, creates a `ClientSession`, calls `session.initialize()`, then `session.call_tool(name, arguments)`.
  - Parses the tool's text content blocks as JSON (handles both single- and multi-block responses).
  - Raises `RuntimeError` with a clear message (including the server URL) if the connection fails — distinguishing "server not running" from other errors.
  - Provides typed wrappers: `ask_graph`, `get_entity_by_label`, `find_relationships`, `extract_from_text`, `ingest_folder`, `get_ingestion_status`, `list_documents`, `submit_feedback`, `get_learning_stats`.
- `pages/chat_tab.py` — **Чат (Chat)**: a text input + history view. Sends questions via `ask_graph` and renders the JSON result.
- `pages/documents_tab.py` — **Документы (Documents)**: lists ingested documents (`list_documents`), with a folder picker (`QFileDialog.getExistingDirectory`) that triggers `ingest_folder` and shows the resulting `IngestionJob` summary.
- `pages/entities_tab.py` — **Сущности (Entities)**: a combo box for entity label (`Party`/`Obligation`/`Risk`/`LegalNorm`), a name filter, and a results table (`get_entity_by_label`). Double-clicking a row looks up its relationships via `find_relationships`.
- `pages/learning_tab.py` — **Learning Brain**: a feedback submission form (`submit_feedback`) and a live stats table (`get_learning_stats`).

## Why a background asyncio loop?

PyQt6's event loop is synchronous, while the `mcp` SDK's SSE client is
`async`. Calling `asyncio.run(...)` directly from the UI thread would block
the GUI for the duration of every MCP call (which can be slow — LLM calls,
graph writes, folder ingestion). `AsyncRunner` solves this by running a
persistent event loop on a separate `QThread`, and a per-call helper thread
that drives a coroutine to completion and reports back via a thread-safe Qt
signal.

## Running

```bash
cd frontend
python app.py
```

Requires the MCP Fabric server running (see [mcp_fabric.md](mcp_fabric.md))
and reachable at `MCP_SERVER_URL` (default `http://localhost:8000/sse`).

## Module imports

The frontend uses **flat, non-package-style imports** (e.g.
`from main_window import MainWindow`, `import mcp_client`,
`from async_runner import AsyncRunner`), so it must be run from inside the
`frontend/` directory (`python app.py`), not as `python -m frontend.app`
from the repo root.
