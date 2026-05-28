"""Sanity tests for package import and metadata."""

import leathercam


def test_version_exposed() -> None:
    assert isinstance(leathercam.__version__, str)
    assert leathercam.__version__.count(".") >= 1
