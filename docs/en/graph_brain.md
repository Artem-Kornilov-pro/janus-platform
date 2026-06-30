# Graph Brain

**Path**: `core/graph_brain/`

The Graph Brain owns the Neo4j knowledge graph for the Lex domain: its
ontology (schema), the GraphRAG extraction that turns structured documents
into graph data, and the async client used to read/write the graph.

## Files

- `schema.py` — the Lex ontology:
  - **Node labels**: `Document`, `Clause`, `Party`, `Obligation`, `Risk`, `LegalNorm`, `CourtDecision`, `Invoice`, `Deadline`, `Claim`
  - **Relationship types**: `CONTAINS`, `REGULATES`, `VIOLATES`, `REFERENCES`, `PRECEDENT_FOR`, `OBLIGATES`, `HAS_RISK`, `INVOLVES`, `ISSUES`, `BILLED_TO`, `HAS_DEADLINE`, `BINDS`, `HAS_CLAIM`, `FILED_BY`, `FILED_AGAINST`
  - Typical relationships:
    - `(Document)-[:CONTAINS]->(Clause)`
    - `(Clause)-[:REGULATES|VIOLATES|REFERENCES]->(LegalNorm | CourtDecision)`
    - `(CourtDecision)-[:PRECEDENT_FOR]->(Clause|Document)`
    - `(Party)-[:OBLIGATES]->(Obligation)-[:OBLIGATES]->(Party)` (owed-by / owed-to)
    - `(Clause)-[:HAS_RISK]->(Risk)`
    - `(Document)-[:INVOLVES]->(Party)`
    - `(Clause)-[:CONTAINS]->(Invoice)`, `(Party)-[:ISSUES]->(Invoice)-[:BILLED_TO]->(Party)` — invoices for the **Финансы (Finance)** tab
    - `(Clause)-[:HAS_DEADLINE]->(Deadline)-[:BINDS]->(Party)` — contractual/statutory deadlines for the **Юрист (Legal)** tab
    - `(Document)-[:HAS_CLAIM]->(Claim)`, `(Claim)-[:FILED_BY|FILED_AGAINST]->(Party)`, `(Claim)-[:REFERENCES]->(Obligation)` — legal claims/pretensions (претензии)
  - `CONSTRAINT_STATEMENTS` / `INDEX_STATEMENTS` — uniqueness constraints (e.g. `Document.id`, `LegalNorm.code`, `Invoice.id`, `Deadline.id`, `Claim.id`) and full-text indexes (e.g. `Clause.title`/`content`, `Risk.description`).
  - `all_setup_statements()` — combines the Lex statements with the Learning Brain's `FEEDBACK_CONSTRAINT` and the Ingestion Pipeline's `JOB_CONSTRAINT` (imported lazily to avoid circular imports).

- `neo4j_client.py` — `Neo4jClient`, an async wrapper around the Neo4j driver (`neo4j.AsyncGraphDatabase`):
  - `setup_schema()` — runs `all_setup_statements()`.
  - `create_document_node`, `create_clause`, `create_entity`, `create_relationship` — individual write helpers.
  - `write_graph(nodes, relationships)` — **batch transactional write**: takes lists of node/relationship dicts (as produced by `graph_rag.build_graph`) and writes them all in one transaction using `MERGE` (idempotent on re-ingestion).
  - `find_risks_for_document`, `find_document_by_hash`, `list_documents`, `get_entity_by_label`, `find_relationships` — read helpers used by MCP tools.
  - `get_risk_report`, `get_obligations_by_party`, `get_deadlines`, `list_invoices` — domain-specific reports backing the **Юрист**/**Финансы** frontend tabs (see [mcp_fabric.md](mcp_fabric.md)).
  - `run_read_query(cypher, parameters)` — runs an arbitrary (read-only, enforced upstream by `nl2cypher`) Cypher query and returns rows as dicts.
  - `_run_write` — internal helper; uses a proper `async def _tx_func(tx): await tx.run(...)` pattern required by the async Neo4j driver (a naive `session.execute_write(lambda tx: tx.run(...))` does not await correctly).

- `graph_rag.py` — GraphRAG extraction:
  - `ClauseAnalysis` (pydantic) — per-clause LLM output: `obligations`, `risks`, `referenced_norms`, `violated_norms`.
  - `analyze_clause(section, client=None, extra_instructions="")` — sends one document section/clause to the LLM and parses a `ClauseAnalysis`. `extra_instructions` is where the Learning Brain injects "lessons learned" from human feedback (see [learning_brain.md](learning_brain.md)).
  - `build_graph(document_id, document, client=None, extra_instructions="")` — iterates over a `StructuredDocument`'s sections, calls `analyze_clause` for each, and assembles two lists: `nodes` and `relationships` (plain dicts ready for `Neo4jClient.write_graph`).

## Data flow

```
StructuredDocument (from Document Brain)
   │
   ▼
graph_rag.build_graph(document_id, document, extra_instructions=...)
   │   for each section/clause:
   │     analyze_clause() ──▶ LLM ──▶ ClauseAnalysis
   │                                    (obligations, risks, norms, violations)
   ▼
(nodes: list[dict], relationships: list[dict])
   │
   ▼
Neo4jClient.write_graph(nodes, relationships)  ──▶ Neo4j (MERGE, transactional)
```

## Reads

All graph reads exposed to MCP clients go through `Neo4jClient`:
- Direct lookups (`get_entity_by_label`, `find_relationships`, `list_documents`) — simple, safe, parameterized Cypher.
- Open-ended natural-language questions (`ask_graph` in MCP Fabric) go through `core/mcp_fabric/nl2cypher.py`, which asks the LLM to produce **read-only** Cypher (any `CREATE`/`MERGE`/`DELETE`/`SET`/`REMOVE`/`DROP`/`CALL` is rejected before execution), then runs it via `Neo4jClient.run_read_query`.

## Configuration

- `NEO4J_URI` (default `bolt://localhost:7687`)
- `NEO4J_USER` (default `neo4j`)
- `NEO4J_PASSWORD` (required)

Neo4j itself runs as the Docker container `janus-neo4j` (image `neo4j:5.26`,
see `docker-compose.yml`), with ports `7474` (browser/HTTP) and `7687`
(Bolt) exposed.
