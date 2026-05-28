"""Pytest configuration. Ensures Qt runs headless in CI."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
