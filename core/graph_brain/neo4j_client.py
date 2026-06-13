"""Async Neo4j client for the Lex knowledge graph.

Provides typed helper methods for creating documents, clauses, entities
and relationships, plus a batch-insert helper that writes an entire
extracted graph within a single transaction.
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncManagedTransaction

from core.graph_brain.schema import all_setup_statements


class Neo4jClient:
    """Thin async wrapper around the Neo4j driver for the Lex domain."""

    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j"):
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        self._database = database

    async def close(self) -> None:
        await self._driver.close()

    async def setup_schema(self) -> None:
        """Create constraints and indexes required by the Lex ontology."""
        async with self._driver.session(database=self._database) as session:
            for statement in all_setup_statements():
                await session.run(statement)

    # ------------------------------------------------------------------
    # Single-entity helpers
    # ------------------------------------------------------------------

    async def create_document_node(self, document_id: str, properties: dict[str, Any]) -> None:
        query = (
            "MERGE (d:Document {id: $id}) "
            "SET d += $properties"
        )
        await self._run_write(query, id=document_id, properties=properties)

    async def create_clause(self, clause_id: str, document_id: str, properties: dict[str, Any]) -> None:
        query = (
            "MERGE (c:Clause {id: $id}) "
            "SET c += $properties "
            "WITH c "
            "MATCH (d:Document {id: $document_id}) "
            "MERGE (d)-[:CONTAINS]->(c)"
        )
        await self._run_write(query, id=clause_id, document_id=document_id, properties=properties)

    async def create_entity(self, label: str, key_property: str, key_value: str, properties: dict[str, Any]) -> None:
        """Create or update a node of an arbitrary label, matched on one key property."""
        query = (
            f"MERGE (n:{label} {{{key_property}: $key_value}}) "
            "SET n += $properties"
        )
        await self._run_write(query, key_value=key_value, properties=properties)

    async def create_relationship(
        self,
        from_label: str,
        from_key: str,
        from_value: str,
        to_label: str,
        to_key: str,
        to_value: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        query = (
            f"MATCH (a:{from_label} {{{from_key}: $from_value}}) "
            f"MATCH (b:{to_label} {{{to_key}: $to_value}}) "
            f"MERGE (a)-[r:{rel_type}]->(b) "
            "SET r += $properties"
        )
        await self._run_write(
            query,
            from_value=from_value,
            to_value=to_value,
            properties=properties or {},
        )

    # ------------------------------------------------------------------
    # Batch insert
    # ------------------------------------------------------------------

    async def write_graph(self, nodes: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> None:
        """Write a batch of nodes and relationships in a single transaction.

        Each node dict must have: label, key_property, key_value, properties.
        Each relationship dict must have: from_label, from_key, from_value,
        to_label, to_key, to_value, rel_type, properties (optional).
        """
        async with self._driver.session(database=self._database) as session:
            await session.execute_write(self._write_graph_tx, nodes, relationships)

    @staticmethod
    async def _write_graph_tx(
        tx: AsyncManagedTransaction,
        nodes: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
    ) -> None:
        for node in nodes:
            query = (
                f"MERGE (n:{node['label']} {{{node['key_property']}: $key_value}}) "
                "SET n += $properties"
            )
            await tx.run(query, key_value=node["key_value"], properties=node.get("properties", {}))

        for rel in relationships:
            query = (
                f"MATCH (a:{rel['from_label']} {{{rel['from_key']}: $from_value}}) "
                f"MATCH (b:{rel['to_label']} {{{rel['to_key']}: $to_value}}) "
                f"MERGE (a)-[r:{rel['rel_type']}]->(b) "
                "SET r += $properties"
            )
            await tx.run(
                query,
                from_value=rel["from_value"],
                to_value=rel["to_value"],
                properties=rel.get("properties", {}),
            )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def find_risks_for_document(self, document_id: str) -> list[dict[str, Any]]:
        query = (
            "MATCH (d:Document {id: $document_id})-[:CONTAINS]->(c:Clause)-[:HAS_RISK]->(r:Risk) "
            "RETURN c.id AS clause_id, c.title AS clause_title, r.description AS risk, r.severity AS severity"
        )
        async with self._driver.session(database=self._database) as session:
            result = await session.run(query, document_id=document_id)
            return [record.data() async for record in result]

    async def get_entity_by_label(self, label: str, name: str) -> list[dict[str, Any]]:
        """Find nodes of a given label whose name/title/id/code contains `name`."""
        query = (
            f"MATCH (n:{label}) "
            "WHERE toLower(coalesce(n.name, '')) CONTAINS toLower($name) "
            "   OR toLower(coalesce(n.title, '')) CONTAINS toLower($name) "
            "   OR toLower(coalesce(n.id, '')) CONTAINS toLower($name) "
            "   OR toLower(coalesce(n.code, '')) CONTAINS toLower($name) "
            "RETURN n"
        )
        async with self._driver.session(database=self._database) as session:
            result = await session.run(query, name=name)
            return [dict(record["n"]) async for record in result]

    async def find_relationships(self, source: str, target: str) -> list[dict[str, Any]]:
        """Find relationships between any nodes matching `source` and `target` by name/title/id/code."""
        query = (
            "MATCH (a)-[r]->(b) "
            "WHERE (toLower(coalesce(a.name, '')) CONTAINS toLower($source) "
            "       OR toLower(coalesce(a.title, '')) CONTAINS toLower($source) "
            "       OR toLower(coalesce(a.id, '')) CONTAINS toLower($source) "
            "       OR toLower(coalesce(a.code, '')) CONTAINS toLower($source)) "
            "  AND (toLower(coalesce(b.name, '')) CONTAINS toLower($target) "
            "       OR toLower(coalesce(b.title, '')) CONTAINS toLower($target) "
            "       OR toLower(coalesce(b.id, '')) CONTAINS toLower($target) "
            "       OR toLower(coalesce(b.code, '')) CONTAINS toLower($target)) "
            "RETURN labels(a) AS source_labels, a AS source, type(r) AS relationship, "
            "       labels(b) AS target_labels, b AS target"
        )
        async with self._driver.session(database=self._database) as session:
            result = await session.run(query, source=source, target=target)
            return [record.data() async for record in result]

    async def run_read_query(self, cypher: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Run an arbitrary read-only Cypher query and return the records as dicts."""
        async with self._driver.session(database=self._database) as session:
            result = await session.run(cypher, parameters or {})
            return [record.data() async for record in result]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_write(self, query: str, **params: Any) -> None:
        async def _tx_func(tx: AsyncManagedTransaction) -> None:
            await tx.run(query, **params)

        async with self._driver.session(database=self._database) as session:
            await session.execute_write(_tx_func)
