"""Reward model: turns raw feedback into per-entity-type quality metrics.

The "reward" for a single feedback item is +1 for a correct extraction and
-1 for an incorrect one. Aggregated over all feedback for an entity type,
this gives a simple precision metric that the prompt optimizer and active
learner use to decide where the Graph Brain needs the most improvement.
"""

from __future__ import annotations

from pydantic import BaseModel


class EntityTypeStats(BaseModel):
    entity_type: str
    total: int
    correct: int
    incorrect: int

    @property
    def precision(self) -> float:
        if self.total == 0:
            return 1.0
        return self.correct / self.total

    @property
    def reward(self) -> int:
        return self.correct - self.incorrect


def reward_for_feedback(feedback: dict) -> int:
    """+1 if the extraction was correct, -1 otherwise."""
    return 1 if feedback["is_correct"] else -1


def compute_stats(feedback_items: list[dict]) -> dict[str, EntityTypeStats]:
    """Group feedback by entity_type and compute precision/reward per type."""
    stats: dict[str, EntityTypeStats] = {}

    for item in feedback_items:
        entity_type = item["entity_type"]
        if entity_type not in stats:
            stats[entity_type] = EntityTypeStats(entity_type=entity_type, total=0, correct=0, incorrect=0)

        s = stats[entity_type]
        s.total += 1
        if item["is_correct"]:
            s.correct += 1
        else:
            s.incorrect += 1

    return stats


def weakest_entity_types(stats: dict[str, EntityTypeStats], min_samples: int = 3) -> list[str]:
    """Return entity types with the lowest precision, ordered worst-first.

    Types with fewer than `min_samples` feedback items are excluded - there
    isn't enough signal yet to act on.
    """
    eligible = [s for s in stats.values() if s.total >= min_samples]
    eligible.sort(key=lambda s: s.precision)
    return [s.entity_type for s in eligible if s.precision < 1.0]
