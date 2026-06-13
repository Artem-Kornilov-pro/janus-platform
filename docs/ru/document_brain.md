# Document Brain

**Путь**: `core/document_brain/`

Document Brain превращает «сырые» файлы (PDF, сканы и т.д.) в
структурированное, типизированное представление документа, с которым
может работать остальная система.

## Файлы

- `models.py` — pydantic-модели:
  - `TextBlock`, `PageExtraction`, `DocumentExtraction` (с методом `full_text()`, который склеивает все страницы/блоки в один текст)
  - `DocumentSection`
  - `StructuredDocument` — итоговый результат: `document_type`, `title`, `parties`, `dates`, `sections` (список `DocumentSection`), `summary`
- `extractor.py` — `extract_document(file_path)`:
  - Использует **pdfplumber** для извлечения нативного текста и таблиц со страниц PDF.
  - Для страниц без извлекаемого текста (например, отсканированные изображения) использует **pytesseract** (Tesseract OCR) + **Pillow** как запасной вариант.
  - Возвращает `DocumentExtraction`.
- `structurer.py`:
  - `structure_text(text, client=None)` — отправляет «сырой» текст в LLM с инструкцией сформировать `StructuredDocument` в виде JSON, затем валидирует через pydantic.
  - `structure_document(extraction, client=None)` — удобная обёртка, вызывающая `structure_text` на `extraction.full_text()`.

## LLM-клиент

**Путь**: `core/llm/`

- `client.py`:
  - `get_client()` возвращает экземпляр `openai.OpenAI`, настроенный на OpenAI-совместимый эндпоинт **Yandex Cloud** (`base_url="https://ai.api.cloud.yandex.net/v1"`), с авторизацией через `YANDEX_CLOUD_API_KEY` и `project=YANDEX_CLOUD_FOLDER`.
  - `_model_uri()` формирует URI вида `gpt://{folder}/{model}` из `YANDEX_CLOUD_FOLDER` и `YANDEX_CLOUD_MODEL` (модель по умолчанию: `deepseek-v4-flash/latest`).
  - `complete(instructions, input_text, max_output_tokens=4096, temperature=0.3, client=None)` вызывает `client.responses.create(...)` (**Responses API**) и возвращает `response.output_text`.
- `json_utils.py`:
  - `parse_json_response(raw)` убирает Markdown-обёртку ```` ```json ```` (LLM любят её добавлять) через regex, затем выполняет `json.loads`.

Все вызовы LLM в проекте (структурирование в Document Brain, извлечение
GraphRAG в Graph Brain, перевод NL→Cypher в MCP Fabric, оптимизация
промптов в Learning Brain) проходят через `complete()` +
`parse_json_response()`, поэтому модель/провайдера можно поменять в
одном месте.

## Как это связано между собой

```
файл (PDF/DOCX/TXT/MD/RTF)
   │
   ▼
extractor.extract_document()  ──▶ DocumentExtraction (страницы, блоки, таблицы)
   │
   ▼
structurer.structure_document() ──▶ LLM (core.llm.client.complete)
   │                                    │
   │                                    ▼
   │                              JSON → parse_json_response → StructuredDocument
   ▼
StructuredDocument (document_type, title, parties, dates, sections, summary)
   │
   ▼
используется GraphRAG из Graph Brain (build_graph) для создания узлов/связей графа
```

## Примечания

- Для **конвейера загрузки** «сырой» текст берётся из `core/ingestion_pipeline/extractors.py` (поддерживает больше форматов: PDF/DOCX/TXT/MD/RTF), а не из `document_brain/extractor.py`. `extractor.py` в Document Brain ориентирован на PDF + OCR, а `structurer.structure_text()` — общий шаг LLM-структурирования, используемый в обоих путях.
- Кириллица в консоли Windows PowerShell может отображаться нечитаемо (`?`/мусорные символы) из-за кодовой страницы консоли — данные, хранящиеся в Neo4j, при этом корректны и в UTF-8.
