# Learning Brain

**Path**: `core/learning_brain/`

The Learning Brain closes the human-in-the-loop feedback cycle: it stores
corrections from users, turns them into per-entity-type quality metrics, and
feeds "lessons learned" back into the GraphRAG extraction prompts so future
extractions improve.

## Files

- `feedback_model.py`:
  - `Feedback` (pydantic) — `id`, `document_id`, `clause_id`, `entity_id`, `entity_type`, `original_value`, `is_correct`, `corrected_value`, timestamp.
  - `FEEDBACK_CONSTRAINT` — Neo4j uniqueness constraint on `Feedback.id` (folded into `graph_brain.schema.all_setup_statements()`).
  - `store_feedback(client, feedback)` — writes a `:Feedback` node.
  - `list_feedback(client)` — reads back all feedback (ordered by timestamp).

- `reward_model.py`:
  - `EntityTypeStats` (pydantic) — `total`, `correct`, `incorrect`, `precision`, `reward` for one entity type.
  - `compute_stats(feedback_items)` — aggregates a list of `Feedback` into `EntityTypeStats` per `entity_type`. `reward` is a simple signal (e.g. `correct - incorrect`) used to rank entity types.
  - `weakest_entity_types(stats)` — sorts entity types by reward/precision to find where the model is currently weakest.

- `prompt_optimizer.py`:
  - `build_augmented_prompt(entity_type, feedback_items)` — turns a set of incorrect extractions (with their corrections) into a "lessons learned" text block, e.g. *"Previously, X was misclassified as Y; the correct value is Z. Pay attention to..."*.
  - `retrain_prompts(client, entity_type=None)` — fetches feedback, computes stats, picks the weakest entity type(s) (or a specific one), and returns an `extra_instructions` string. This string is passed straight into `graph_rag.analyze_clause(..., extra_instructions=...)` / `build_graph(..., extra_instructions=...)`, so the next extraction's LLM prompt is augmented with concrete examples of past mistakes.

- `active_learner.py`:
  - `select_for_review(client, per_type_limit=2)` — runs `ENTITY_QUERIES` for `Obligation`, `Risk`, `LegalNorm` to sample a small, diverse set of extracted entities that haven't been reviewed yet, for a human to label via `feedback_cli.py`. This is a simple diversity-sampling active-learning strategy.

- `feedback_cli.py` (project root) — an interactive CLI: lists extracted entities (via `active_learner.select_for_review`), asks the user whether each extraction is correct, and calls `submit_feedback` (the same path used by the MCP tool / frontend's Learning Brain tab).

## The feedback loop

```
                ┌─────────────────────────────┐
                │  Extraction (graph_rag)       │
                │  uses extra_instructions from │
                │  retrain_prompts()             │
                └──────────────┬────────────────┘
                                │ produces entities (Obligation/Risk/LegalNorm/...)
                                ▼
                ┌─────────────────────────────┐
                │  Human review                 │
                │  - feedback_cli.py (terminal)│
                │  - Frontend "Learning Brain"  │
                │    tab (submit_feedback)      │
                └──────────────┬────────────────┘
                                │ Feedback nodes in Neo4j
                                ▼
                ┌─────────────────────────────┐
                │  reward_model.compute_stats   │
                │  → precision/reward per type  │
                └──────────────┬────────────────┘
                                │
                                ▼
                ┌─────────────────────────────┐
                │  prompt_optimizer             │
                │  .retrain_prompts()           │
                │  → "lessons learned" prompt   │
                │     augmentation              │
                └──────────────┬────────────────┘
                                │
                                └────────────────▶ back into graph_rag.build_graph(extra_instructions=...)
```

`MCP Fabric`'s `extract_from_text` and `ingest_folder` both call
`retrain_prompts(client)` before extraction, so every new extraction
automatically benefits from accumulated feedback.

## Frontend integration

The PyQt6 **Learning Brain** tab (`frontend/pages/learning_tab.py`) provides:
- A form to submit feedback (`submit_feedback` MCP tool) with fields for
  document/clause/entity IDs, entity type, original value, corrected value,
  and a correctness checkbox.
- A live stats table (`get_learning_stats`) showing total/correct/incorrect
  counts, precision, and reward per entity type.
