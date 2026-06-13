"""Ad-hoc check of the Learning Brain against a live Neo4j instance."""

import asyncio

from core.mcp_fabric.server import _get_client, get_learning_stats, submit_feedback
from core.learning_brain.prompt_optimizer import retrain_prompts


async def main():
    print("=== submit_feedback (a few examples) ===")
    print(await submit_feedback(
        document_id="contract-14-2026",
        clause_id="contract-14-2026:clause:2",
        entity_id="contract-14-2026:clause:2:risk:0",
        entity_type="Risk",
        original_value="Высокая пеня 0.5% в день",
        is_correct=False,
        corrected_value="Пеня 0.5% в день за просрочку оплаты, лимит 100% суммы договора - проверить на кабальность по ст. 333 ГК РФ",
    ))
    print(await submit_feedback(
        document_id="contract-14-2026",
        clause_id="contract-14-2026:clause:2",
        entity_id="contract-14-2026:clause:2:risk:1",
        entity_type="Risk",
        original_value="Неопределенность форс-мажора",
        is_correct=False,
        corrected_value="Отсутствует перечень форс-мажорных обстоятельств - риск споров о применимости",
    ))
    print(await submit_feedback(
        document_id="contract-14-2026",
        clause_id="contract-14-2026:clause:1",
        entity_id="contract-14-2026:clause:1:risk:0",
        entity_type="Risk",
        original_value="Нарушение срока поставки",
        is_correct=True,
    ))

    print("\n=== get_learning_stats ===")
    print(await get_learning_stats())

    print("\n=== retrain_prompts (augmentation) ===")
    client = _get_client()
    try:
        augmentation = await retrain_prompts(client)
    finally:
        await client.close()
    print(augmentation)


asyncio.run(main())
