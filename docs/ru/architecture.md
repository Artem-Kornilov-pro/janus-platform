# Janus Platform — Обзор архитектуры

Janus Platform построена по принципу «Core + Domains»: общее, не зависящее
от предметной области ядро (понимание документов, граф знаний, цикл
обучения на обратной связи, MCP-фабрика данных и конвейер загрузки) плюс
подключаемые модули доменов. Первый домен — **Lex** (юридический: договоры,
пункты, обязательства, риски, нормы права, судебные решения).

## Общая схема

```
                        ┌─────────────────────────┐
                        │  Десктоп-фронтенд PyQt6   │
                        │  (Чат / Документы /       │
                        │   Сущности / Learning)    │
                        └────────────┬─────────────┘
                                      │ MCP по SSE
                                      ▼
                        ┌─────────────────────────┐
                        │       MCP Fabric          │
                        │  (FastMCP + SSE-сервер)   │
                        └──┬───────┬──────────┬────┘
                            │       │          │
              ┌─────────────┘       │          └──────────────┐
              ▼                     ▼                          ▼
   ┌─────────────────────┐ ┌──────────────────┐   ┌─────────────────────┐
   │   Document Brain      │ │   Graph Brain     │   │   Learning Brain     │
   │ (извлечение + LLM-    │ │ (онтология Neo4j, │   │ (фидбэк, награды,    │
   │  структурирование)    │ │  запись GraphRAG, │   │  оптимизация         │
   │                       │ │  NL→Cypher чтение)│   │  промптов, active    │
   │                       │ │                   │   │  learning)           │
   └───────────┬───────────┘ └─────────┬─────────┘   └──────────┬──────────┘
               │                        │                         │
               │                        ▼                         │
               │              ┌──────────────────┐                │
               └─────────────▶│ Конвейер загрузки │◀──────────────┘
                               │ (извлечение →     │
                               │  чанкинг → граф →  │
                               │  трекинг)          │
                               └─────────┬──────────┘
                                          ▼
                                  ┌───────────────┐
                                  │     Neo4j      │
                                  │   (Docker)     │
                                  └───────────────┘

   Все обращения к LLM идут через `core/llm/client.py` — используется
   OpenAI-совместимый Responses API Yandex Cloud (модель:
   deepseek-v4-flash/latest).
```

## Компоненты

| Компонент | Путь | Назначение | Документация |
|---|---|---|---|
| Document Brain | `core/document_brain/` | Извлечение из PDF/OCR + структурирование через LLM в типизированную модель документа | [document_brain.md](document_brain.md) |
| Graph Brain | `core/graph_brain/` | Онтология Neo4j, извлечение GraphRAG, асинхронный клиент графа | [graph_brain.md](graph_brain.md) |
| MCP Fabric | `core/mcp_fabric/` | Сервер FastMCP/SSE, предоставляющий все инструменты клиентам | [mcp_fabric.md](mcp_fabric.md) |
| Learning Brain | `core/learning_brain/` | Хранение фидбэка людей, модель награды, оптимизация промптов, active learning | [learning_brain.md](learning_brain.md) |
| Конвейер загрузки | `core/ingestion_pipeline/` | Извлечение из разных форматов, чанкинг, пакетная запись в граф, трекинг заданий, наблюдение за папками | [ingestion_pipeline.md](ingestion_pipeline.md) |
| Фронтенд | `frontend/` | Десктоп-интерфейс PyQt6, общающийся с MCP Fabric по SSE | [frontend.md](frontend.md) |
| LLM-клиент | `core/llm/` | Общая абстракция над LLM (Yandex Cloud, OpenAI-совместимый API) | см. [document_brain.md](document_brain.md#llm-клиент) |

## Используемые технологии

- **Язык**: Python 3.12+
- **Граф знаний**: Neo4j 5.26 (Docker-контейнер `janus-neo4j`)
- **Парсинг документов**: `pdfplumber` (нативный текст/таблицы PDF), `pytesseract` + `pillow` (OCR как запасной вариант), `python-docx`, `striprtf`
- **Валидация данных**: `pydantic` v2 (все структурированные модели)
- **LLM-провайдер**: Yandex Cloud, OpenAI-совместимый Responses API через SDK `openai`, модель `deepseek-v4-flash/latest`
- **Протокол**: Model Context Protocol (MCP) через Python SDK `mcp`, сервер на Server-Sent Events (SSE) через `FastMCP`
- **Наблюдение за папками**: `watchdog`
- **Фронтенд**: PyQt6 (десктоп), с фоновым asyncio-циклом, который связывает асинхронный MCP-клиент с циклом событий Qt
- **Тестирование**: `pytest` + `pytest-asyncio`
- **Упаковка/конфигурация**: `pyproject.toml`, `requirements.txt`, `docker-compose.yml`, `.env` / `.env.example`

## Типичный сценарий: вопрос в чате

1. Пользователь вводит вопрос на вкладке **Чат** в PyQt6.
2. `frontend/async_runner.py` запускает `frontend/mcp_client.ask_graph(question)` в фоновом asyncio-цикле, чтобы не блокировать UI-поток Qt.
3. `mcp_client` открывает SSE-соединение с сервером MCP Fabric (`http://localhost:8000/sse`) и вызывает инструмент `ask_graph`.
4. Сервер (`core/mcp_fabric/server.py`) обращается к `core/mcp_fabric/nl2cypher.py`, который просит LLM перевести вопрос на естественном языке в **только-читающий** Cypher-запрос (запросы на изменение данных отклоняются).
5. Запрос выполняется в Neo4j через `core/graph_brain/neo4j_client.py`, результат возвращается через MCP в виде JSON обратно во фронтенд.
6. Сигнал Qt `finished` доставляет результат в основной поток, и вкладка «Чат» отображает ответ.

## Типичный сценарий: загрузка документов

1. Пользователь выбирает папку на вкладке **Документы** → вызывается MCP-инструмент `ingest_folder`.
2. `core/ingestion_pipeline/batch_ingester.py` находит поддерживаемые файлы (`extractors.py`), извлекает текст и разбивает его на перекрывающиеся чанки (`chunker.py`).
3. Каждый чанк дедуплицируется по хэшу содержимого, структурируется Document Brain (`structure_text`) и превращается в узлы/связи графа Graph Brain (`build_graph`), которые записываются в Neo4j (`write_graph`).
4. Прогресс отслеживается как узел `IngestionJob` в Neo4j (`tracker.py`) и возвращается во фронтенд.

## Как всё запустить

- **Neo4j**: `docker compose up -d` (по умолчанию запускает только Neo4j).
- **Сервер MCP Fabric**: запускать локально через `python -m core.mcp_fabric.server` (это нужно для загрузки папок, так как сервер должен видеть те же пути файловой системы, что и диалог выбора папки в фронтенде). Контейнеризированный вариант доступен через `docker compose --profile docker up -d`.
- **Фронтенд**: `cd frontend && python app.py`.
- Конфигурация берётся из переменных окружения — см. `.env.example`.
