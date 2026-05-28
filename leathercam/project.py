"""Project (.lcam) file format.

Each project is a single JSON document that bundles:

- The strategy and every form parameter (so the next session opens with
  the same settings).
- The user's source artwork (PNG / JPG / SVG / DXF), base64-encoded
  into the JSON itself. The original file lives inside the save and is
  never required again.
- A small metadata block (version, timestamp, source filename).

Schema:

    {
      "format": "leathercam-project",
      "version": 1,
      "saved_at": "2026-05-28T15:00:00",
      "source": {
        "filename": "logo.svg",
        "encoding": "base64",
        "data": "..."
      },
      "params": {
        ...  # whatever _Parameters.to_dict() produced
      }
    }
"""

from __future__ import annotations

import base64
import datetime as _dt
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

PROJECT_VERSION = 1
PROJECT_FORMAT_TAG = "leathercam-project"


class ProjectError(ValueError):
    pass


@dataclass(frozen=True)
class ProjectData:
    source_filename: str
    source_bytes: bytes
    params: dict[str, Any] = field(default_factory=dict)
    saved_at: str = ""

    def write(self, path: str | Path) -> None:
        save_project(path, self)


def save_project(path: str | Path, project: ProjectData) -> None:
    document = {
        "format": PROJECT_FORMAT_TAG,
        "version": PROJECT_VERSION,
        "saved_at": project.saved_at or _dt.datetime.now().isoformat(timespec="seconds"),
        "source": {
            "filename": project.source_filename,
            "encoding": "base64",
            "data": base64.b64encode(project.source_bytes).decode("ascii"),
        },
        "params": project.params,
    }
    Path(path).write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")


def load_project(path: str | Path) -> ProjectData:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != PROJECT_FORMAT_TAG:
        raise ProjectError("not a LeatherCAM project file")
    version = int(data.get("version", 0))
    if version > PROJECT_VERSION:
        raise ProjectError(f"project version {version} newer than supported {PROJECT_VERSION}")
    source = data.get("source") or {}
    encoding = source.get("encoding", "base64")
    if encoding != "base64":
        raise ProjectError(f"unsupported source encoding: {encoding!r}")
    try:
        source_bytes = base64.b64decode(source["data"], validate=True)
    except (KeyError, ValueError) as exc:
        raise ProjectError(f"invalid embedded source: {exc}") from exc
    return ProjectData(
        source_filename=source.get("filename", ""),
        source_bytes=source_bytes,
        params=dict(asdict_dict(data.get("params"))),
        saved_at=data.get("saved_at", ""),
    )


def asdict_dict(value: Any) -> dict[str, Any]:
    """Coerce ``value`` into a plain dict. Used to normalize the params block."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    try:
        return dict(asdict(value))
    except TypeError as exc:
        raise ProjectError(f"params must be a dict-like object: {exc}") from exc
