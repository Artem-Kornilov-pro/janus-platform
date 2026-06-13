from __future__ import annotations

import json

from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import mcp_client
from async_runner import AsyncRunner


class DocumentsTab(QWidget):
    """List ingested documents and trigger folder ingestion."""

    def __init__(self, runner: AsyncRunner) -> None:
        super().__init__()
        self._runner = runner
        self._pending: dict[str, str] = {}  # call_id -> kind

        self.document_list = QListWidget()

        self.refresh_button = QPushButton("Обновить список")
        self.refresh_button.clicked.connect(self.refresh)

        self.ingest_button = QPushButton("Загрузить папку...")
        self.ingest_button.clicked.connect(self._choose_folder)

        button_row = QHBoxLayout()
        button_row.addWidget(self.refresh_button)
        button_row.addWidget(self.ingest_button)

        self.status_box = QTextEdit()
        self.status_box.setReadOnly(True)
        self.status_box.setPlaceholderText("Статус загрузки появится здесь...")

        layout = QVBoxLayout()
        layout.addLayout(button_row)
        layout.addWidget(self.document_list)
        layout.addWidget(self.status_box)
        self.setLayout(layout)

        self._runner.finished.connect(self._on_finished)
        self.refresh()

    def refresh(self) -> None:
        self.refresh_button.setEnabled(False)
        call_id = self._runner.submit(mcp_client.list_documents)
        self._pending[call_id] = "list"

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку с документами")
        if not folder:
            return

        self.status_box.append(f"Запуск загрузки папки: {folder}")
        self.ingest_button.setEnabled(False)
        call_id = self._runner.submit(lambda: mcp_client.ingest_folder(folder, True))
        self._pending[call_id] = "ingest"

    def _on_finished(self, call_id: str, result: object, error: object) -> None:
        kind = self._pending.pop(call_id, None)
        if kind is None:
            return

        if kind == "list":
            self.refresh_button.setEnabled(True)
            if error is not None:
                QMessageBox.warning(self, "Ошибка", f"Не удалось получить список документов: {error}")
                return
            self.document_list.clear()
            for doc in result or []:
                if not isinstance(doc, dict):
                    self.document_list.addItem(str(doc))
                    continue
                title = doc.get("title") or doc.get("id") or "?"
                doc_type = doc.get("document_type", "")
                self.document_list.addItem(f"{title}  [{doc_type}]  ({doc.get('id', '')})")

        elif kind == "ingest":
            self.ingest_button.setEnabled(True)
            if error is not None:
                self.status_box.append(f"Ошибка загрузки: {error}")
                return
            self.status_box.append(json.dumps(result, ensure_ascii=False, indent=2))
            self.refresh()
