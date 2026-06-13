"""Ad-hoc end-to-end check of MCP Fabric tools against a live Neo4j instance."""

import asyncio
import io
import sys

from core.mcp_fabric.server import (
    ask_graph,
    extract_from_text,
    find_relationships,
    get_entity_by_label,
)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


async def main():
    print("=== A: get_entity_by_label(Party, '') ===")
    parties = await get_entity_by_label("Party", "")
    for p in parties:
        print(" ", p)

    print("\n=== B: find_relationships('Технопром', 'Obligation') ===")
    rels = await find_relationships("Технопром", "Obligation")
    for r in rels:
        print(" ", r["source"].get("name") or r["source"].get("title"), "-[" + r["relationship"] + "]->", r["target"].get("description"))

    print("\n=== C: extract_from_text (new paragraph) ===")
    result = await extract_from_text(
        "Заказчик обязуется оплатить работы в течение 10 дней с момента подписания акта выполненных работ.",
        document_id="addendum-1",
    )
    print(" ", result)

    print("\n=== D: ask_graph('Найди все нормы права, связанные с ответственностью') ===")
    norms = await ask_graph("Найди все нормы права (LegalNorm), связанные с ответственностью сторон")
    for n in norms:
        print(" ", n)

    print("\n=== E: ask_graph('Удали все риски') -> should be refused ===")
    try:
        result = await ask_graph("Удали все узлы Risk из графа")
        print("  UNEXPECTED SUCCESS:", result)
    except ValueError as e:
        print("  Refused as expected:", e)


asyncio.run(main())
