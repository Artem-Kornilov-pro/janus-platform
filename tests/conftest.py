"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest


# ---------------------------------------------------------------------------
# Neo4j live-connection fixture
# ---------------------------------------------------------------------------

def _neo4j_available() -> bool:
    """Return True if a Neo4j instance is reachable at the configured URI."""
    import socket

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    host = uri.split("://")[-1].split(":")[0]
    port_str = uri.split(":")[-1] if ":" in uri.split("://")[-1] else "7687"
    try:
        port = int(port_str)
    except ValueError:
        port = 7687
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


requires_neo4j = pytest.mark.skipif(
    not _neo4j_available(),
    reason="Neo4j not reachable — start janus-neo4j container to run E2E tests",
)


@pytest.fixture(scope="session")
def neo4j_test_creds() -> dict[str, str]:
    return {
        "uri": os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        "user": os.environ.get("NEO4J_USER", "neo4j"),
        "password": os.environ.get("NEO4J_PASSWORD", "janus-pass"),
        "database": "neo4j",
    }


# ---------------------------------------------------------------------------
# Headless Qt application fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qt_app():
    """Single headless QApplication for the whole test session.

    Skipped automatically when PyQt6 is not installed.
    """
    import sys

    pytest.importorskip("PyQt6", reason="PyQt6 not installed — skipping GUI tests")
    from PyQt6.QtWidgets import QApplication  # noqa: PLC0415

    app = QApplication.instance() or QApplication(sys.argv)
    yield app
