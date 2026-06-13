from __future__ import annotations

import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import mcp_client
from async_runner import AsyncRunner


class ChatTab(QWidget):
    """Ask natural-language questions against the knowledge graph (ask_graph)."""

    def __init__(self, runner: AsyncRunner) -> None:
        super().__init__()
        self._runner = runner
        self._pending_calls: set[str] = set()

        self.history = QTextEdit()
        self.history.setReadOnly(True)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Спросите про граф знаний, например: Какие риски есть в договоре 14-2026?")
        self.input.returnPressed.connect(self._send)

        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self._send)

        input_row = QHBoxLayout()
        input_row.addWidget(self.input)
        input_row.addWidget(self.send_button)

        layout = QVBoxLayout()
        layout.addWidget(self.history)
        layout.addLayout(input_row)
        self.setLayout(layout)

        self._runner.finished.connect(self._on_finished)

    def _send(self) -> None:
        question = self.input.text().strip()
        if not question:
            return

        self.history.append(f"<b>Вы:</b> {question}")
        self.input.clear()
        self.input.setEnabled(False)
        self.send_button.setEnabled(False)

        call_id = self._runner.submit(lambda: mcp_client.ask_graph(question))
        self._pending_calls.add(call_id)

    def _on_finished(self, call_id: str, result: object, error: object) -> None:
        if call_id not in self._pending_calls:
            return
        self._pending_calls.discard(call_id)

        if error is not None:
            self.history.append(f"<b>Ошибка:</b> {error}")
        else:
            text = json.dumps(result, ensure_ascii=False, indent=2)
            self.history.append(f"<b>Janus:</b><pre>{text}</pre>")

        self.input.setEnabled(True)
        self.send_button.setEnabled(True)
        self.input.setFocus(Qt.FocusReason.OtherFocusReason)
