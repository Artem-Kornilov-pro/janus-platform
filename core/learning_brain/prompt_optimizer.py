"""Prompt Optimizer: turns accumulated feedback into prompt augmentations.

This is the "RL" part of the Learning Brain in its simplest useful form:
instead of updating model weights, it rewrites the instructions given to
the LLM for the next extraction run, based on what humans corrected last
time (a form of in-context policy improvement).
"""

from __future__ import annotations

from core.learning_brain.reward_model import compute_stats, weakest_entity_types

MAX_EXAMPLES_PER_TYPE = 3


def _format_correction_example(item: dict) -> str:
    return (
        f'- For a "{item["entity_type"]}", the extractor previously produced:\n'
        f'    {item["original_value"]!r}\n'
        f'  but the correct extraction was:\n'
        f'    {item["corrected_value"]!r}'
    )


def build_augmented_prompt(base_prompt: str, feedback_items: list[dict]) -> str:
    """Append a "lessons learned" section to `base_prompt` based on feedback.

    - For entity types where extractions have been corrected, include up to
      MAX_EXAMPLES_PER_TYPE before/after examples (few-shot correction).
    - For entity types with precision < 1.0 and enough samples, add an
      explicit instruction to pay closer attention.
    """
    if not feedback_items:
        return base_prompt

    stats = compute_stats(feedback_items)
    weak_types = weakest_entity_types(stats)

    corrections = [item for item in feedback_items if not item["is_correct"] and item.get("corrected_value")]
    if not corrections and not weak_types:
        return base_prompt

    sections = ["\n\n--- Lessons learned from human feedback ---"]

    if weak_types:
        sections.append(
            "Pay extra attention to these entity types, which have been "
            f"frequently mis-extracted: {', '.join(weak_types)}."
        )

    examples_by_type: dict[str, list[dict]] = {}
    for item in corrections:
        examples_by_type.setdefault(item["entity_type"], []).append(item)

    for entity_type, examples in examples_by_type.items():
        sections.append(f"\nCorrection examples for {entity_type}:")
        for item in examples[:MAX_EXAMPLES_PER_TYPE]:
            sections.append(_format_correction_example(item))

    return base_prompt + "\n".join(sections)


async def retrain_prompts(client, entity_type: str | None = None) -> str:
    """Fetch all stored feedback and build an augmented prompt section.

    Returns just the augmentation text (empty string if no feedback yet),
    which callers append to their base system prompt.
    """
    from core.learning_brain.feedback_model import list_feedback

    feedback_items = await list_feedback(client, entity_type=entity_type)
    augmented = build_augmented_prompt("", feedback_items)
    return augmented
