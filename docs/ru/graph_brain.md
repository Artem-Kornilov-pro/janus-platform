# Graph Brain

**Путь**: `core/graph_brain/`

Graph Brain отвечает за граф знаний Neo4j домена Lex: его онтологию (схему),
извлечение GraphRAG, превращающее структурированные документы в данные
графа, и асинхронный клиент для чтения/записи графа.

## Файлы

- `schema.py` — онтология Lex:
  - **Метки узлов**: `Document`, `Clause`, `Party`, `Obligation`, `Risk`, `LegalNorm`, `CourtDecision`
  - **Типы связей**: `CONTAINS`, `REGULATES`, `VIOLATES`, `REFERENCES`, `PRECEDENT_FOR`, `OBLIGATES`, `HAS_RISK`, `INVOLVES`
  - Типичные связи:
    - `(Document)-[:CONTAINS]->(Clause)`
    - `(Clause)-[:REGULATES|VIOLATES|REFERENCES]->(LegalNorm | CourtDecision)`
    - `(CourtDecision)-[:PRECEDENT_FOR]->(Clause|Document)`
    - `(Party)-[:OBLIGATES]->(Obligation)-[:OBLIGATES]->(Party)` (кто должен / кому должен)
    - `(Clause)-[:HAS_RISK]->(Risk)`
    - `(Document)-[:INVOLVES]->(Party)`
  - `CONSTRAINT_STATEMENTS` / `INDEX_STATEMENTS` — ограничения уникальности (например, `Document.id`, `LegalNorm.code`) и полнотекстовые индексы (например, `Clause.title`/`content`, `Risk.description`).
  - `all_setup_statements()` — объединяет операторы Lex с `FEEDBACK_CONSTRAINT` из Learning Brain и `JOB_CONSTRAINT` из конвейера загрузки (импортируются лениво, чтобы избежать циклических импортов).

- `neo4j_client.py` — `Neo4jClient`, асинхронная обёртка над драйвером Neo4j (`neo4j.AsyncGraphDatabase`):
  - `setup_schema()` — выполняет `all_setup_statements()`.
  - `create_document_node`, `create_clause`, `create_entity`, `create_relationship` — отдельные хелперы для записи.
  - `write_graph(nodes, relationships)` — **пакетная транзакционная запись**: принимает списки словарей узлов/связей (как их формирует `graph_rag.build_graph`) и записывает их в одной транзакции через `MERGE` (идемпотентно при повторной загрузке).
  - `find_risks_for_document`, `find_document_by_hash`, `list_documents`, `get_entity_by_label`, `find_relationships` — хелперы чтения, используемые MCP-инструментами.
  - `run_read_query(cypher, parameters)` — выполняет произвольный (только чтение, проверяется выше по стеку в `nl2cypher`) Cypher-запрос и возвращает строки в виде словарей.
  - `_run_write` — внутренний хелпер; использует корректный паттерн `async def _tx_func(tx): await tx.run(...)`, необходимый асинхронному драйверу Neo4j (наивный `session.execute_write(lambda tx: tx.run(...))` не дожидается выполнения корректно).

- `graph_rag.py` — извлечение GraphRAG:
  - `ClauseAnalysis` (pydantic) — результат LLM по одному пункту/clause: `obligations`, `risks`, `referenced_norms`, `violated_norms`.
  - `analyze_clause(section, client=None, extra_instructions="")` — отправляет один раздел/пункт документа в LLM и парсит `ClauseAnalysis`. В `extra_instructions` Learning Brain вставляет «извлечённые уроки» из фидбэка людей (см. [learning_brain.md](learning_brain.md)).
  - `build_graph(document_id, document, client=None, extra_instructions="")` — проходит по разделам `StructuredDocument`, вызывает `analyze_clause` для каждого и собирает два списка: `nodes` и `relationships` (обычные словари, готовые для `Neo4jClient.write_graph`).

## Поток данных

```
StructuredDocument (от Document Brain)
   │
   ▼
graph_rag.build_graph(document_id, document, extra_instructions=...)
   │   для каждого раздела/пункта:
   │     analyze_clause() ──▶ LLM ──▶ ClauseAnalysis
   │                                    (обязательства, риски, нормы, нарушения)
   ▼
(nodes: list[dict], relationships: list[dict])
   │
   ▼
Neo4jClient.write_graph(nodes, relationships)  ──▶ Neo4j (MERGE, транзакционно)
```

## Чтение данных

Все операции чтения графа, доступные MCP-клиентам, идут через `Neo4jClient`:
- Прямые запросы (`get_entity_by_label`, `find_relationships`, `list_documents`) — простой, безопасный, параметризованный Cypher.
- Произвольные вопросы на естественном языке (`ask_graph` в MCP Fabric) идут через `core/mcp_fabric/nl2cypher.py`, который просит LLM сформировать **только-читающий** Cypher (любой `CREATE`/`MERGE`/`DELETE`/`SET`/`REMOVE`/`DROP`/`CALL` отклоняется до выполнения), затем выполняет его через `Neo4jClient.run_read_query`.

## Конфигурация

- `NEO4J_URI` (по умолчанию `bolt://localhost:7687`)
- `NEO4J_USER` (по умолчанию `neo4j`)
- `NEO4J_PASSWORD` (обязателен)

Сам Neo4j работает как Docker-контейнер `janus-neo4j` (образ `neo4j:5.26`,
см. `docker-compose.yml`), с открытыми портами `7474` (браузер/HTTP) и
`7687` (Bolt).
