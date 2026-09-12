"""The job spec: what to export, from where, under what name.

Everything that decides the shape of a run lives in a YAML file rather than in
the script, because the script is the same on every project and the YAML is
not. It is also the thing a reviewer can read without opening ArcGIS Pro.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Any

import yaml

VALID_FORMATS = {"pdf", "png", "jpg", "tiff"}


class JobError(ValueError):
    """A job spec that cannot be run, with a message that says why."""


@dataclass
class ExportSettings:
    formats: list[str] = field(default_factory=lambda: ["pdf"])
    dpi: int = 300
    georeferenced_pdf: bool = True
    embed_fonts: bool = True

    def __post_init__(self) -> None:
        self.formats = [f.lower() for f in self.formats]
        bad = sorted(set(self.formats) - VALID_FORMATS)
        if bad:
            raise JobError(f"unsupported export format(s): {bad}")
        if not self.formats:
            raise JobError("at least one export format is required")
        if not 50 <= self.dpi <= 1200:
            raise JobError(f"dpi {self.dpi} is outside the sensible range 50-1200")


@dataclass
class Job:
    """One map production run."""

    project: str                     # path to the .aprx
    layout: str                      # layout name inside the project
    output_dir: str
    index_layer: str | None = None   # layer driving the map series
    name_field: str | None = None    # field used in the output name
    where: str | None = None         # definition query on the index layer
    name_template: str = "{layout}_{name}"
    export: ExportSettings = field(default_factory=ExportSettings)
    required_elements: list[str] = field(default_factory=list)
    overwrite: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Job":
        data = dict(data)

        for key in ("project", "layout", "output_dir"):
            if not data.get(key):
                raise JobError(f"'{key}' is required")

        export_data = data.pop("export", {}) or {}
        if not isinstance(export_data, dict):
            raise JobError("'export' must be a mapping")

        unknown_export = set(export_data) - set(ExportSettings.__dataclass_fields__)
        if unknown_export:
            raise JobError(f"unknown key(s) under 'export': {sorted(unknown_export)}")

        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise JobError(f"unknown key(s) in job: {sorted(unknown)}")

        job = cls(export=ExportSettings(**export_data), **data)

        # A map series needs both halves, or neither.
        if bool(job.index_layer) != bool(job.name_field):
            raise JobError(
                "'index_layer' and 'name_field' must be given together "
                "(or both left out, for a single-page layout)"
            )
        return job

    @classmethod
    def load(cls, path: str | pathlib.Path) -> "Job":
        path = pathlib.Path(path)
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise JobError(f"{path} is not valid YAML: {exc}") from exc
        if not isinstance(data, dict):
            raise JobError(f"{path} does not contain a job mapping")
        return cls.from_dict(data)

    @property
    def is_map_series(self) -> bool:
        return self.index_layer is not None
