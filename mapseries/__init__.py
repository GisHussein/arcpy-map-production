"""Batch map production for ArcGIS Pro, with the pre-flight checks that stop a
400-page run from failing on page 340."""

from .job import ExportSettings, Job, JobError
from .naming import render, slugify, unique
from .qa import LayoutIssue, check_required_elements, check_scale, check_text_elements

__version__ = "0.1.0"

__all__ = [
    "Job",
    "JobError",
    "ExportSettings",
    "slugify",
    "render",
    "unique",
    "LayoutIssue",
    "check_required_elements",
    "check_text_elements",
    "check_scale",
]
