# Конвейер загрузки (Ingestion Pipeline)

**Путь**: `core/ingestion_pipeline/`

Конвейер загрузки принимает папку (или один файл) с документами и
прогоняет их через извлечение → чанкинг → структурирование Document Brain →
GraphRAG Graph Brain → Neo4j, с дедупликацией, повторными попытками,
обработкой ошибок и отслеживанием прогресса.

## Файлы

- `extractors.py`:
  - `extract_text(path)` — извлекает «сырой» текст из `.pdf`, `.docx`, `.txt`, `.md`, `.rtf` (используя `pdfplumber`, `python-docx`, `striprtf`, обычное чтение файлов).
  - `discover_documents(folder, recursive)` — обходит папку и возвращает все файлы с поддерживаемыми расширениями.
  - `UnsupportedFileTypeError` — выбрасывается для неподдерживаемых расширений.

- `chunker.py`:
  - `chunk_text(text, max_chars=6000, overlap_chars=400)` — разбивает текст на чанки с учётом абзацев. Абзацы по возможности остаются целыми; каждый чанк включает `overlap_chars` символов «хвоста» предыдущего чанка, чтобы сущности/пункты, находящиеся на границе чанков, не терялись. Абзацы длиннее `max_chars` разбиваются «жёстко».

- `tracker.py`:
  - `IngestionJob` (pydantic) — `id`, `status` (`pending`/`running`/`completed`/`failed`), `source_path`, `total_files`, `processed_files`, `skipped_files`, `total_chunks`, `processed_chunks`, `errors`, `created_at`, `updated_at`.
  - `JOB_CONSTRAINT` — ограничение уникальности Neo4j на `IngestionJob.id`.
  - `create_job`, `update_job`, `get_job` — сохраняют/читают состояние задания как узлы `:IngestionJob` в Neo4j, поэтому прогресс сохраняется между вызовами MCP.

- `batch_ingester.py`:
  - `content_hash(text)` — SHA-256 хэш нормализованного текста, используется для дедупликации.
  - `_with_retry` — оборачивает вызовы LLM/графа повторными попытками с экспоненциальной задержкой.
  - `ingest_chunk(client, document_id, chunk_text, ..., extra_instructions)` — выполняет `structure_text` → `build_graph` → `write_graph` для одного чанка.
  - `ingest_file(client, path, job, ...)` — извлекает текст, разбивает на чанки, пропускает чанки, чей `content_hash` уже есть в графе (`find_document_by_hash`), и загружает остальные.
  - `ingest_paths(client, paths, source_path)` — общая оркестрация по нескольким файлам; создаёт/обновляет `IngestionJob`, один раз заранее вызывает `retrain_prompts` и продолжает работу при ошибках по отдельным файлам (они записываются в `job.errors`).
  - `ingest_folder(client, path, recursive=True)` — `discover_documents` + `ingest_paths`.

- `watcher.py`:
  - `watch_folder(...)` — использует `watchdog` для наблюдения за папкой на предмет новых/изменённых файлов и автоматического запуска загрузки (для сценария «положите файлы здесь», независимо от вызова MCP `ingest_folder`).

- `janus_ingest.py` (корень проекта) — CLI:
  - `--folder <path> [--recursive]` — загрузить папку.
  - `--file <path>` — загрузить один файл.
  - `--status <job_id>` — проверить статус задания.

## Поток выполнения

```
discover_documents(folder)
   │
   ▼
для каждого файла:
  extract_text(path)
   │
   ▼
  chunk_text(text)
   │
   ▼
  для каждого чанка:
    content_hash(chunk) ──▶ уже есть в графе? ──да──▶ пропустить (skipped_files++)
       │ нет
       ▼
    structure_text(chunk)  ──▶ StructuredDocument
       │
       ▼
    build_graph(doc_id, structured, extra_instructions=retrain_prompts(...))
       │
       ▼
    write_graph(nodes, relationships)  ──▶ Neo4j
       │
       ▼
    update_job(processed_chunks += 1, processed_files += 1, ...)
```

Ошибки в любом отдельном файле/чанке перехватываются, добавляются в
`job.errors`, и обработка продолжается со следующим файлом — повреждённый
документ не прерывает весь пакет.

## Интеграция с MCP

`ingest_folder` и `get_ingestion_status` доступны как MCP-инструменты (см.
[mcp_fabric.md](mcp_fabric.md)) и используются вкладкой **Документы** во
фронтенде. `list_documents` (также MCP) читает узлы `:Document`, записанные
во время загрузки.

## Известное ограничение

При повторной загрузке папки, часть файлов которой уже была загружена,
дедупликация может пропустить не **все** дубликаты (только часть) —
дедупликация по хэшу содержимого сейчас работает на уровне чанков и
зависит от точного совпадения границ чанков между запусками. Это известная
задача на доработку, пока не исправлена полностью.
