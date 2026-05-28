"""Tests for the .lcam project file format."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from leathercam.project import (
    PROJECT_FORMAT_TAG,
    PROJECT_VERSION,
    ProjectData,
    ProjectError,
    load_project,
    save_project,
)


def test_round_trip_preserves_bytes_filename_and_params(tmp_path: Path) -> None:
    project = ProjectData(
        source_filename="logo.svg",
        source_bytes=b"<svg></svg>",
        params={"strategy": "pocket", "depth_mm": 0.4},
    )
    out = tmp_path / "x.lcam"
    save_project(out, project)
    loaded = load_project(out)
    assert loaded.source_filename == "logo.svg"
    assert loaded.source_bytes == b"<svg></svg>"
    assert loaded.params["strategy"] == "pocket"
    assert loaded.params["depth_mm"] == 0.4


def test_round_trip_handles_binary_source(tmp_path: Path) -> None:
    binary = bytes(range(256))
    project = ProjectData(source_filename="x.png", source_bytes=binary)
    out = tmp_path / "x.lcam"
    save_project(out, project)
    loaded = load_project(out)
    assert loaded.source_bytes == binary


def test_save_writes_expected_top_level_keys(tmp_path: Path) -> None:
    out = tmp_path / "x.lcam"
    save_project(out, ProjectData(source_filename="a", source_bytes=b""))
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["format"] == PROJECT_FORMAT_TAG
    assert doc["version"] == PROJECT_VERSION
    assert "saved_at" in doc
    assert doc["source"]["encoding"] == "base64"


def test_load_rejects_non_project_json(tmp_path: Path) -> None:
    out = tmp_path / "x.lcam"
    out.write_text(json.dumps({"format": "something-else"}), encoding="utf-8")
    with pytest.raises(ProjectError):
        load_project(out)


def test_load_rejects_future_version(tmp_path: Path) -> None:
    out = tmp_path / "x.lcam"
    doc = {
        "format": PROJECT_FORMAT_TAG,
        "version": PROJECT_VERSION + 99,
        "source": {"filename": "x", "encoding": "base64", "data": ""},
        "params": {},
    }
    out.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ProjectError):
        load_project(out)


def test_load_rejects_unsupported_encoding(tmp_path: Path) -> None:
    out = tmp_path / "x.lcam"
    doc = {
        "format": PROJECT_FORMAT_TAG,
        "version": PROJECT_VERSION,
        "source": {"filename": "x", "encoding": "gzip", "data": ""},
        "params": {},
    }
    out.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ProjectError):
        load_project(out)


def test_load_rejects_corrupt_base64(tmp_path: Path) -> None:
    out = tmp_path / "x.lcam"
    doc = {
        "format": PROJECT_FORMAT_TAG,
        "version": PROJECT_VERSION,
        "source": {"filename": "x", "encoding": "base64", "data": "!@#$%not-base64"},
        "params": {},
    }
    out.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ProjectError):
        load_project(out)


def test_method_write_matches_save_function(tmp_path: Path) -> None:
    project = ProjectData(source_filename="x.svg", source_bytes=b"data")
    path = tmp_path / "via-method.lcam"
    project.write(path)
    loaded = load_project(path)
    assert loaded.source_bytes == b"data"


def test_saved_at_can_be_preserved(tmp_path: Path) -> None:
    project = ProjectData(source_filename="x", source_bytes=b"", saved_at="2026-05-28T10:00:00")
    out = tmp_path / "x.lcam"
    save_project(out, project)
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["saved_at"] == "2026-05-28T10:00:00"
