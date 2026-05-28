"""Application entry point."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from platformdirs import user_log_dir


def _configure_logging() -> Path:
    """Send logs to both the console and a rotating file in the user log dir."""
    log_dir = Path(user_log_dir("leathercam"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "leathercam.log"

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        file_handler = RotatingFileHandler(
            log_path, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        stream = logging.StreamHandler()
        stream.setFormatter(fmt)
        root.addHandler(stream)
    root.setLevel(logging.INFO)
    return log_path


def main(argv: list[str] | None = None) -> int:
    log_path = _configure_logging()
    logging.getLogger(__name__).info("LeatherCAM starting; log file: %s", log_path)

    from PySide6.QtWidgets import QApplication

    from leathercam.ui.main_window import MainWindow

    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("LeatherCAM")
    app.setOrganizationName("leathercam")

    window = MainWindow()
    window.show()
    return app.exec()
