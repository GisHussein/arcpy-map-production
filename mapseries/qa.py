"""Pre-flight checks on a layout, before anything is rendered.

A 400-page series takes the better part of an hour. Discovering afterwards that
the scale bar was deleted in someone else's edit, or that a dynamic text element
still reads ``<dyn type="page" property="name"/>`` because the index layer was
renamed, costs that hour twice.

These functions take plain data - lists of element names, strings of text - so
they can be tested without ArcGIS Pro. The ArcPy layer hands them what it finds
in the layout and does nothing else.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# What a map going to a client is expected to carry.
DEFAULT_REQUIRED = ["title", "scalebar", "north_arrow", "legend", "credits"]

# Placeholder text that means "nobody filled this in".
_PLACEHOLDER = re.compile(
    r"^\s*(text|new text|title|<dyn[^>]*>|lorem ipsum|tbd|todo|xxx+)\s*$",
    re.IGNORECASE,
)


@dataclass
class LayoutIssue:
    severity: str   # "error" or "warning"
    code: str
    message: str


def normalise(name: str) -> str:
    """Match element names loosely: 'North Arrow', 'north_arrow', 'NorthArrow'."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def check_required_elements(
    present: list[str],
    required: list[str] | None = None,
) -> list[LayoutIssue]:
    """Every element the job says a finished map must have."""
    required = required or DEFAULT_REQUIRED
    have = {normalise(name) for name in present}

    issues = []
    for wanted in required:
        if normalise(wanted) not in have:
            issues.append(
                LayoutIssue(
                    severity="error",
                    code="layout.missing_element",
                    message=f"layout has no element matching '{wanted}'",
                )
            )
    return issues


def check_text_elements(texts: dict[str, str]) -> list[LayoutIssue]:
    """Catch unfilled and unresolved text before it reaches a client."""
    issues = []
    for name, value in texts.items():
        value = (value or "").strip()
        if not value:
            issues.append(
                LayoutIssue(
                    severity="warning",
                    code="layout.empty_text",
                    message=f"text element '{name}' is empty",
                )
            )
        elif _PLACEHOLDER.match(value):
            issues.append(
                LayoutIssue(
                    severity="error",
                    code="layout.placeholder_text",
                    message=f"text element '{name}' still reads '{value}'",
                )
            )
    return issues


def check_scale(scale: float | None, allowed: list[float] | None = None) -> list[LayoutIssue]:
    """Round-number scales, because 1:23,847 is not a scale anyone asked for.

    A map frame left on whatever scale the last zoom produced is the clearest
    sign that a layout was exported without being looked at.
    """
    if scale is None:
        return [
            LayoutIssue(
                severity="warning",
                code="layout.unknown_scale",
                message="map frame scale could not be read",
            )
        ]

    allowed = allowed or [500, 1000, 2500, 5000, 10000, 25000, 50000,
                          100000, 250000, 500000, 1000000]
    if not any(abs(scale - value) / value < 0.001 for value in allowed):
        return [
            LayoutIssue(
                severity="warning",
                code="layout.odd_scale",
                message=f"map frame is at 1:{scale:,.0f}, not one of the standard scales",
            )
        ]
    return []


def summarise(issues: list[LayoutIssue]) -> tuple[int, int]:
    errors = sum(1 for issue in issues if issue.severity == "error")
    warnings = sum(1 for issue in issues if issue.severity == "warning")
    return errors, warnings
