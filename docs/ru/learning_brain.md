# Learning Brain

**Путь**: `core/learning_brain/`

Learning Brain замыкает цикл обратной связи с человеком: сохраняет
исправления пользователей, превращает их в метрики качества по типам
сущностей и передаёт «извлечённые уроки» обратно в промпты извлечения
GraphRAG, чтобы будущие извлечения становились точнее.

## Файлы

- `feedback_model.py`:
  - `Feedback` (pydantic) — `id`, `document_id`, `clause_id`, `entity_id`, `entity_type`, `original_value`, `is_correct`, `corrected_value`, временная метка.
  - `FEEDBACK_CONSTRAINT` — ограничение уникальности Neo4j на `Feedback.id` (включается в `graph_brain.schema.all_setup_statements()`).
  - `store_feedback(client, feedback)` — записывает узел `:Feedback`.
  - `list_feedback(client)` — читает весь сохранённый фидбэк (упорядоченный по времени).

- `reward_model.py`:
  - `EntityTypeStats` (pydantic) — `total`, `correct`, `incorrect`, `precision`, `reward` для одного типа сущности.
  - `compute_stats(feedback_items)` — агрегирует список `Feedback` в `EntityTypeStats` по каждому `entity_type`. `reward` — простой сигнал (например, `correct - incorrect`), используемый для ранжирования типов сущностей.
  - `weakest_entity_types(stats)` — сортирует типы сущностей по награде/точности, чтобы найти, где модель сейчас работает хуже всего.

- `prompt_optimizer.py`:
  - `build_augmented_prompt(entity_type, feedback_items)` — превращает набор неверных извлечений (с их исправлениями) в текстовый блок «извлечённых уроков», например: *«Ранее X было ошибочно классифицировано как Y; правильное значение — Z. Обратите внимание на...»*.
  - `retrain_prompts(client, entity_type=None)` — получает фидбэк, считает статистику, выбирает самый «слабый» тип(ы) сущности (или конкретный) и возвращает строку `extra_instructions`. Эта строка передаётся прямо в `graph_rag.analyze_clause(..., extra_instructions=...)` / `build_graph(..., extra_instructions=...)`, поэтому промпт LLM для следующего извлечения дополняется конкретными примерами прошлых ошибок.

- `active_learner.py`:
  - `select_for_review(client, per_type_limit=2)` — выполняет `ENTITY_QUERIES` для `Obligation`, `Risk`, `LegalNorm`, чтобы выбрать небольшую разнообразную выборку извлечённых сущностей, которые ещё не проверены человеком, для разметки через `feedback_cli.py`. Это простая стратегия active learning на основе разнообразия выборки.

- `feedback_cli.py` (корень проекта) — интерактивный CLI: показывает извлечённые сущности (через `active_learner.select_for_review`), спрашивает пользователя, верно ли извлечение, и вызывает `submit_feedback` (тот же путь, что использует MCP-инструмент / вкладка Learning Brain во фронтенде).

## Цикл обратной связи

```
                ┌─────────────────────────────┐
                │  Извлечение (graph_rag)       │
                │  использует extra_instructions │
                │  из retrain_prompts()          │
                └──────────────┬────────────────┘
                                │ создаёт сущности (Obligation/Risk/LegalNorm/...)
                                ▼
                ┌─────────────────────────────┐
                │  Проверка человеком           │
                │  - feedback_cli.py (терминал) │
                │  - вкладка «Learning Brain»   │
                │    во фронтенде (submit_feedback)│
                └──────────────┬────────────────┘
                                │ узлы Feedback в Neo4j
                                ▼
                ┌─────────────────────────────┐
                │  reward_model.compute_stats   │
                │  → точность/награда по типам  │
                └──────────────┬────────────────┘
                                │
                                ▼
                ┌─────────────────────────────┐
                │  prompt_optimizer              │
                │  .retrain_prompts()            │
                │  → дополнение промпта          │
                │    «извлечёнными уроками»      │
                └──────────────┬────────────────┘
                                │
                                └────────────────▶ обратно в graph_rag.build_graph(extra_instructions=...)
```

`extract_from_text` и `ingest_folder` из MCP Fabric перед извлечением
вызывают `retrain_prompts(client)`, поэтому каждое новое извлечение
автоматически выигрывает от накопленного фидбэка.

## Интеграция с фронтендом

Вкладка **Learning Brain** в PyQt6 (`frontend/pages/learning_tab.py`)
предоставляет:
- Форму отправки фидбэка (MCP-инструмент `submit_feedback`) с полями для
  ID документа/пункта/сущности, типа сущности, исходного значения,
  исправленного значения и флажка корректности.
- Таблицу статистики в реальном времени (`get_learning_stats`),
  показывающую количество всего/верных/неверных, точность и награду по
  каждому типу сущности.
