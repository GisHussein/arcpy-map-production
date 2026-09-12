"""Output file names.

Map names come from attribute values, and attribute values contain slashes,
Arabic text, trailing spaces and the occasional newline. A name that is merely
"mostly safe" produces a run that fails on page 340 of 400, after forty minutes
of rendering.
"""

from __future__ import annotations

import re
import unicodedata

# Reserved on Windows, where ArcGIS Pro runs.
_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_COLLAPSE = re.compile(r"[\s_]+")

MAX_STEM = 120  # leaves room for a long output directory inside MAX_PATH


def slugify(value: object, fallback: str = "unnamed") -> str:
    """Turn an attribute value into a safe, readable file-name component.

    Non-Latin text is transliterated where possible and otherwise dropped, so
    an Arabic place name yields a usable stem instead of an empty one.
    """
    if value is None:
        return fallback

    text = str(value).strip()
    if not text:
        return fallback

    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = _UNSAFE.sub(" ", text)
    text = _COLLAPSE.sub("_", text).strip("._")

    # Drop anything that is not word-ish after transliteration.
    text = re.sub(r"[^A-Za-z0-9_\-.]", "", text)
    text = _COLLAPSE.sub("_", text).strip("._")

    if not text:
        return fallback
    if text.upper().split(".")[0] in _RESERVED:
        text = f"{text}_map"
    return text[:MAX_STEM]


def render(template: str, tokens: dict[str, object], fallback: str = "unnamed") -> str:
    """Fill ``{token}`` placeholders, slugifying every value.

    Unknown tokens are an error rather than a silently empty string: finding
    out that 400 files are called ``sheet__`` is a bad way to learn about a
    typo in the template.
    """
    used = set(re.findall(r"\{(\w+)\}", template))
    missing = sorted(used - set(tokens))
    if missing:
        raise KeyError(f"template uses unknown token(s): {missing}")

    safe = {key: slugify(value, fallback) for key, value in tokens.items()}
    return slugify(template.format(**safe), fallback)


def unique(stem: str, taken: set[str]) -> str:
    """Return a stem that is not already in ``taken``, and record it.

    Two districts called "Al Qusayr" in the same index layer is normal. Letting
    the second overwrite the first is not.
    """
    candidate = stem
    counter = 2
    while candidate.lower() in taken:
        candidate = f"{stem}_{counter}"
        counter += 1
    taken.add(candidate.lower())
    return candidate
