# Фронтенд (десктоп на PyQt6)

**Путь**: `frontend/`

Десктопный GUI на **PyQt6**, который подключается к серверу MCP Fabric по
SSE и предоставляет доступ к его инструментам через четыре вкладки.

## Файлы

- `app.py` — точка входа: создаёт `QApplication`, показывает `MainWindow`, запускает цикл событий.
- `main_window.py` — `MainWindow` (`QMainWindow`): владеет единственным экземпляром `AsyncRunner` и `QTabWidget` с четырьмя вкладками ниже.
- `async_runner.py` — `AsyncRunner`: связывает асинхронные вызовы MCP с Qt.
  - Запускает выделенный фоновый цикл событий `asyncio` в `QThread`.
  - `submit(coro_factory)` планирует корутину в этом цикле из недолговечного вспомогательного потока (`asyncio.run_coroutine_threadsafe(...).result()`), затем испускает сигнал Qt `finished(call_id, result, error)` — Qt автоматически доставляет этот сигнал в **основной поток**, поэтому код UI никогда не трогает виджеты из фонового потока.
  - Каждая страница генерирует `call_id`, вызывает `submit(...)` и фильтрует события `finished` по этому id.
- `mcp_client.py` — тонкая асинхронная обёртка над SDK `mcp`:
  - `call_tool(name, arguments)` открывает соединение `sse_client(MCP_SERVER_URL)`, создаёт `ClientSession`, вызывает `session.initialize()`, затем `session.call_tool(name, arguments)`.
  - Разбирает текстовые блоки результата инструмента как JSON (обрабатывает как ответы из одного блока, так и из нескольких).
  - Если соединение не удалось, выбрасывает `RuntimeError` с понятным сообщением (включая URL сервера) — отличая «сервер не запущен» от прочих ошибок.
  - Предоставляет типизированные обёртки: `ask_graph`, `get_entity_by_label`, `find_relationships`, `extract_from_text`, `ingest_folder`, `get_ingestion_status`, `list_documents`, `submit_feedback`, `get_learning_stats`.
- `pages/chat_tab.py` — **Чат**: поле ввода текста + история сообщений. Отправляет вопросы через `ask_graph` и отображает результат в JSON.
- `pages/documents_tab.py` — **Документы**: список загруженных документов (`list_documents`), диалог выбора папки (`QFileDialog.getExistingDirectory`), запускающий `ingest_folder`, и отображение итоговой сводки `IngestionJob`.
- `pages/entities_tab.py` — **Сущности**: выпадающий список метки сущности (`Party`/`Obligation`/`Risk`/`LegalNorm`), фильтр по имени и таблица результатов (`get_entity_by_label`). Двойной клик по строке показывает связи через `find_relationships`.
- `pages/learning_tab.py` — **Learning Brain**: форма отправки фидбэка (`submit_feedback`) и таблица статистики в реальном времени (`get_learning_stats`).

## Почему нужен фоновый цикл asyncio?

Цикл событий PyQt6 синхронный, а SSE-клиент SDK `mcp` — `async`. Прямой
вызов `asyncio.run(...)` из UI-потока заблокировал бы интерфейс на время
каждого MCP-вызова (а они могут быть медленными — вызовы LLM, запись в граф,
загрузка папок). `AsyncRunner` решает это, запуская постоянный цикл событий
в отдельном `QThread`, и вспомогательный поток на каждый вызов, который
доводит корутину до завершения и сообщает результат через потокобезопасный
сигнал Qt.

## Запуск

```bash
cd frontend
python app.py
```

Требуется запущенный сервер MCP Fabric (см. [mcp_fabric.md](mcp_fabric.md)),
доступный по адресу `MCP_SERVER_URL` (по умолчанию `http://localhost:8000/sse`).

## Импорты модулей

Фронтенд использует **плоские импорты без структуры пакета** (например,
`from main_window import MainWindow`, `import mcp_client`,
`from async_runner import AsyncRunner`), поэтому его нужно запускать из
директории `frontend/` (`python app.py`), а не как `python -m frontend.app`
из корня репозитория.
