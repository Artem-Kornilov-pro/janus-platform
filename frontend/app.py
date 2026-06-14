from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from main_window import MainWindow


def _load_stylesheet() -> str:
    style_path = Path(__file__).resolve().parent / "style.qss"
    return style_path.read_text(encoding="utf-8")


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(_load_stylesheet())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
