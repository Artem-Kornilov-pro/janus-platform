# MCP Fabric

**Путь**: `core/mcp_fabric/`

MCP Fabric — единая точка входа для любого внешнего клиента (фронтенд PyQt6,
Claude Desktop, Cursor и т.д.), позволяющая работать с графом знаний Janus
Lex. Сервер построен на **FastMCP** (`mcp.server.fastmcp.FastMCP`) и
работает по протоколу **Server-Sent Events (SSE)**.

## Файлы

- `server.py` — определяет FastMCP-сервер `"janus-lex-graph"` и регистрирует
  все инструменты (см. ниже). Точка входа: `python -m core.mcp_fabric.server`.
- `nl2cypher.py` — `question_to_cypher(question, client=None)`: отправляет
  вопрос пользователя на естественном языке в LLM с инструкцией составить
  **только-читающий** Cypher-запрос + параметры. Перед выполнением
  сгенерированный запрос проверяется по списку запрещённых слов для записи
  (`CREATE`, `MERGE`, `DELETE`, `SET`, `REMOVE`, `DROP`, `CALL`) и
  отклоняется при их наличии — это защитный механизм, позволяющий `ask_graph`
  выполнять произвольные запросы, сгенерированные LLM, без риска для графа.
- `claude_desktop_config.example.json` — пример конфигурации MCP-клиента,
  указывающего на `http://localhost:8000/sse`, для прямого подключения
  Claude Desktop/Cursor к серверу.

## Инструменты (tools)

| Инструмент | На основе | Описание |
|---|---|---|
| `get_entity_by_label(label, name)` | `Neo4jClient.get_entity_by_label` | Поиск узлов заданной метки (`Party`, `Obligation`, `Risk`, `LegalNorm` и т.д.) по совпадению имени/названия/id/кода. |
| `find_relationships(source, target)` | `Neo4jClient.find_relationships` | Поиск связей между двумя именованными сущностями. |
| `extract_from_text(text, document_id=None)` | Document Brain `structure_text` + Graph Brain `build_graph` + `write_graph` | Запускает полный конвейер извлечения на «сыром» тексте и записывает результат в граф. |
| `ask_graph(question)` | `nl2cypher.question_to_cypher` + `run_read_query` | Вопросы на естественном языке к графу, переводимые в только-читающий Cypher. |
| `submit_feedback(document_id, clause_id, entity_id, entity_type, original_value, is_correct, corrected_value=None)` | Learning Brain `store_feedback` | Запись фидбэка человека по извлечённой сущности. |
| `get_learning_stats()` | Learning Brain `compute_stats` | Точность/награда по типам сущностей на основе сохранённого фидбэка. |
| `ingest_folder(path, recursive=True)` | Конвейер загрузки `ingest_folder` | Извлекает, разбивает на чанки и заносит в граф все поддерживаемые документы из папки; возвращает сводку `IngestionJob`. |
| `get_ingestion_status(job_id)` | Конвейер загрузки `get_job` | Статус ранее запущенного задания загрузки. |
| `list_documents()` | `Neo4jClient.list_documents` | Список всех документов, находящихся в графе. |

Каждый инструмент открывает собственный `Neo4jClient` (через `_get_client()`,
который читает переменные окружения `NEO4J_*`) и закрывает его после
выполнения.

## Конфигурация

| Переменная окружения | По умолчанию | Назначение |
|---|---|---|
| `NEO4J_URI` | `bolt://localhost:7687` | Bolt-адрес Neo4j |
| `NEO4J_USER` | `neo4j` | Пользователь Neo4j |
| `NEO4J_PASSWORD` | *(обязателен)* | Пароль Neo4j |
| `MCP_TRANSPORT` | `sse` | Транспорт (`sse` для HTTP/SSE-клиентов) |
| `MCP_HOST` | `127.0.0.1` | Адрес для биндинга (в Docker — `0.0.0.0`) |
| `MCP_PORT` | `8000` | Порт для биндинга |
| `YANDEX_CLOUD_FOLDER`, `YANDEX_CLOUD_API_KEY`, `YANDEX_CLOUD_MODEL` | — | Реквизиты LLM, используются `extract_from_text`, `ask_graph`, загрузкой документов |

> **Примечание**: `host`/`port` у `FastMCP` — это аргументы конструктора с
> жёстко заданными значениями по умолчанию, они **не** читают переменные
> окружения `FASTMCP_HOST`/`FASTMCP_PORT`. `server.py` самостоятельно читает
> `MCP_HOST`/`MCP_PORT` и передаёт их явно в `FastMCP(...)`.

## Запуск

```bash
# локально (необходимо, чтобы ingest_folder видел локальные пути файловой системы)
python -m core.mcp_fabric.server

# или через Docker (опционально; ingest_folder не увидит пути хоста)
docker compose --profile docker up -d
```

SSE-эндпоинт: `http://<host>:8000/sse`.

## Почему для загрузки папок нужен локальный сервер

`ingest_folder(path)` принимает путь в файловой системе. Если MCP-сервер
работает в Docker-контейнере, у него своя файловая система, и он не может
прочитать пути вида `D:/data`, выбранные через нативный диалог выбора папки
фронтенда на Windows. Для локальной разработки всегда запускайте MCP-сервер
как обычный Python-процесс на той же машине/файловой системе, что и
фронтенд.
