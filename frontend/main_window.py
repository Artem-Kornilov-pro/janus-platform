from __future__ import annotations

from PyQt6.QtWidgets import QMainWindow, QTabWidget

from async_runner import AsyncRunner
from pages.chat_tab import ChatTab
from pages.documents_tab import DocumentsTab
from pages.entities_tab import EntitiesTab
from pages.finance_tab import FinanceTab
from pages.graph_tab import GraphTab
from pages.learning_tab import LearningTab


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Janus Platform - Lex")
        self.resize(1000, 700)

        self.runner = AsyncRunner()

        tabs = QTabWidget()
        tabs.addTab(ChatTab(self.runner), "Чат")
        tabs.addTab(DocumentsTab(self.runner), "Документы")
        tabs.addTab(EntitiesTab(self.runner), "Сущности")
        tabs.addTab(GraphTab(self.runner), "Граф")
        tabs.addTab(LearningTab(self.runner), "Learning Brain")
        tabs.addTab(FinanceTab(), "Финансы")
        self.setCentralWidget(tabs)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        self.runner.shutdown()
        super().closeEvent(event)
