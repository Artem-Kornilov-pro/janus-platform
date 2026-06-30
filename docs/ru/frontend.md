# Фронтенд (десктоп на PyQt6)

**Путь**: `frontend/`

Десктопный GUI на **PyQt6**, который подключается к серверу MCP Fabric по
SSE и предоставляет доступ к его инструментам через семь вкладок.

## Файлы

- `app.py` — точка входа: создаёт `QApplication`, показывает `MainWindow`, запускает цикл событий.
- `main_window.py` — `MainWindow` (`QMainWindow`): владеет единственным экземпляром `AsyncRunner` и `QTabWidget` с семью вкладками ниже.
- `async_runner.py` — `AsyncRunner`: связывает асинхронные вызовы MCP с Qt.
  - Запускает выделенный фоновый цикл событий `asyncio` в `QThread`.
  - `submit(coro_factory)` планирует корутину в этом цикле из недолговечного вспомогательного потока (`asyncio.run_coroutine_threadsafe(...).result()`), затем испускает сигнал Qt `finished(call_id, result, error)` — Qt автоматически доставляет этот сигнал в **основной поток**, поэтому код UI никогда не трогает виджеты из фонового потока.
  - Каждая страница генерирует `call_id`, вызывает `submit(...)` и фильтрует события `finished` по этому id.
- `mcp_client.py` — тонкая асинхронная обёртка над SDK `mcp`:
  - `call_tool(name, arguments)` открывает соединение `sse_client(MCP_SERVER_URL)`, создаёт `ClientSession`, вызывает `session.initialize()`, затем `session.call_tool(name, arguments)`.
  - Разбирает текстовые блоки результата инструмента как JSON (обрабатывает как ответы из одного блока, так и из нескольких).
  - Если соединение не удалось, выбрасывает `RuntimeError` с понятным сообщением (включая URL сервера) — отличая «сервер не запущен» от прочих ошибок.
  - Предоставляет типизированные обёртки на каждый инструмент MCP: `ask_graph`, `get_entity_by_label`, `find_relationships`, `get_risk_report`, `get_obligations_by_party`, `get_deadlines`, `calculate_vat`, `calculate_usn_tax`, `list_invoices`, `extract_from_text`, `ingest_folder`, `get_ingestion_status`, `list_documents`, `submit_feedback`, `get_learning_stats` (что делает каждый — см. [mcp_fabric.md](mcp_fabric.md)).
- `graph_layout.py` — чистые хелперы без зависимостей от Qt для вкладки **«Граф»**: `build_graph_elements(relationships)` превращает записи `find_relationships` в карту узлов и список рёбер (цвет по метке через `NODE_COLORS`), `circular_layout(node_keys, radius)` размещает узлы равномерно по кругу, `describe_node_connections(key, nodes, edges)` строит текстовое описание связей узла.
- `export_utils.py` — `rows_to_csv(columns, rows)`: рендерит таблицу в текст CSV; используется кнопкой «Экспорт в CSV» на всех вкладках с отчётами.
- `pages/chat_tab.py` — **Чат**: поле ввода текста + история сообщений. Отправляет вопросы через `ask_graph` и отображает результат в JSON.
- `pages/documents_tab.py` — **Документы**: список загруженных документов (`list_documents`), диалог выбора папки (`QFileDialog.getExistingDirectory`), запускающий `ingest_folder`, и отображение итоговой сводки `IngestionJob`.
- `pages/entities_tab.py` — **Сущности**: выпадающий список метки сущности (`Party`/`Obligation`/`Risk`/`LegalNorm`/`Invoice`/`Deadline`/`Claim`), фильтр по имени и таблица результатов (`get_entity_by_label`). Двойной клик по строке показывает связи через `find_relationships`.
- `pages/graph_tab.py` — **Граф**: интерактивная визуализация связей узла на `QGraphicsView` (`find_relationships`), раскладка через `graph_layout.circular_layout` с зумом колесом мыши; клик по узлу показывает его связи в боковой панели (`describe_node_connections`).
- `pages/learning_tab.py` — **Learning Brain**: форма отправки фидбэка (`submit_feedback`) и таблица статистики в реальном времени (`get_learning_stats`).
- `pages/finance_tab.py` — **Финансы**: калькулятор НДС и калькулятор налога по УСН «доходы», работающие напрямую через `domains.finance.tax_calculator` (без обращения к MCP), плюс таблица отчёта по счетам (`list_invoices`) с экспортом в CSV.
- `pages/legal_tab.py` — **Юрист**: вкладка с тремя вложенными отчётами на общем виджете `_ReportTable` с экспортом в CSV — **Риски** (`get_risk_report`, цветовая маркировка по серьёзности), **Обязательства** (`get_obligations_by_party`, фильтр по названию стороны или `*` для всех), **Сроки** (`get_deadlines`, с чекбоксом «только просроченные»).

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
