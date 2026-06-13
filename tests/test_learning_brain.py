from core.learning_brain.feedback_model import Feedback
from core.learning_brain.prompt_optimizer import build_augmented_prompt
from core.learning_brain.reward_model import compute_stats, weakest_entity_types


def _feedback(entity_type: str, is_correct: bool, original="orig", corrected=None) -> dict:
    return Feedback(
        document_id="doc-1",
        clause_id="doc-1:clause:0",
        entity_id=f"{entity_type}-{original}",
        entity_type=entity_type,
        original_value=original,
        is_correct=is_correct,
        corrected_value=corrected,
    ).model_dump()


def test_compute_stats_groups_by_entity_type():
    feedback_items = [
        _feedback("Risk", True),
        _feedback("Risk", True),
        _feedback("Risk", False, corrected="real risk"),
        _feedback("Obligation", True),
    ]

    stats = compute_stats(feedback_items)

    assert stats["Risk"].total == 3
    assert stats["Risk"].correct == 2
    assert stats["Risk"].incorrect == 1
    assert round(stats["Risk"].precision, 2) == 0.67
    assert stats["Obligation"].precision == 1.0


def test_weakest_entity_types_orders_worst_first_and_requires_min_samples():
    feedback_items = [
        _feedback("Risk", False, corrected="x"),
        _feedback("Risk", False, corrected="y"),
        _feedback("Risk", True),
        _feedback("Obligation", False, corrected="z"),  # only 1 sample, below min_samples
    ]

    stats = compute_stats(feedback_items)
    weak = weakest_entity_types(stats, min_samples=3)

    assert weak == ["Risk"]


def test_build_augmented_prompt_includes_corrections_and_weak_types():
    feedback_items = [
        _feedback("Risk", False, original="vague risk", corrected="specific risk: late delivery penalty"),
        _feedback("Risk", False, original="another vague risk", corrected="specific risk: liability cap"),
        _feedback("Risk", True),
    ]

    augmented = build_augmented_prompt("BASE PROMPT", feedback_items)

    assert augmented.startswith("BASE PROMPT")
    assert "Risk" in augmented
    assert "vague risk" in augmented
    assert "specific risk: late delivery penalty" in augmented


def test_build_augmented_prompt_returns_base_when_no_feedback():
    assert build_augmented_prompt("BASE PROMPT", []) == "BASE PROMPT"
