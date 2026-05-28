"""Application entry point."""

from __future__ import annotations

import logging
import sys


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    from PySide6.QtWidgets import QApplication

    from leathercam.ui.main_window import MainWindow

    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("LeatherCAM")
    app.setOrganizationName("leathercam")

    window = MainWindow()
    window.show()
    return app.exec()
