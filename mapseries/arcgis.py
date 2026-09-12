"""The ArcPy half.

Everything that needs ArcGIS Pro lives here and nowhere else, so the rest of the
package can be read, reviewed and tested on a machine that does not have a
licence. ``arcpy`` is imported lazily for the same reason.

Tested manually against ArcGIS Pro 3.x. It is not covered by the test suite -
there is no honest way to unit-test an arcpy call without arcpy, and a mocked
version would only assert that the mock was called.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

from .job import Job
from .naming import render, unique
from .qa import LayoutIssue, check_required_elements, check_scale, check_text_elements


def _arcpy():
    try:
        import arcpy  # noqa: PLC0415 - deliberately lazy
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "arcpy is not available. This command needs to run inside the "
            "ArcGIS Pro Python environment (Pro > Python > 'arcgispro-py3')."
        ) from exc
    return arcpy


@dataclass
class Page:
    name: str
    stem: str
    oid: int


def open_layout(job: Job):
    """Return (project, layout), with a clear message when either is missing."""
    arcpy = _arcpy()

    project_path = pathlib.Path(job.project)
    if not project_path.exists():
        raise FileNotFoundError(f"project not found: {project_path}")

    project = arcpy.mp.ArcGISProject(str(project_path))
    layouts = {layout.name: layout for layout in project.listLayouts()}
    if job.layout not in layouts:
        raise KeyError(
            f"layout '{job.layout}' not in {project_path.name}. "
            f"Available: {sorted(layouts)}"
        )
    return project, layouts[job.layout]


def inspect_layout(job: Job) -> list[LayoutIssue]:
    """Run the pre-flight checks against the real layout."""
    _, layout = open_layout(job)

    element_names = [element.name for element in layout.listElements()]
    issues = check_required_elements(element_names, job.required_elements or None)

    texts = {
        element.name: getattr(element, "text", "")
        for element in layout.listElements("TEXT_ELEMENT")
    }
    issues += check_text_elements(texts)

    frames = layout.listElements("MAPFRAME_ELEMENT")
    if not frames:
        issues.append(
            LayoutIssue("error", "layout.no_map_frame", "layout has no map frame")
        )
    else:
        issues += check_scale(getattr(frames[0], "camera", None) and frames[0].camera.scale)

    return issues


def list_pages(job: Job) -> list[Page]:
    """One Page per feature in the index layer, already named and de-duplicated."""
    arcpy = _arcpy()
    _, layout = open_layout(job)

    if not job.is_map_series:
        stem = render(job.name_template, {"layout": job.layout, "name": job.layout})
        return [Page(name=job.layout, stem=stem, oid=-1)]

    frames = layout.listElements("MAPFRAME_ELEMENT")
    if not frames:
        raise RuntimeError("layout has no map frame to drive the series from")

    layers = {layer.name: layer for layer in frames[0].map.listLayers()}
    if job.index_layer not in layers:
        raise KeyError(
            f"index layer '{job.index_layer}' not in the map. Available: {sorted(layers)}"
        )

    index_layer = layers[job.index_layer]
    fields = [field.name for field in arcpy.ListFields(index_layer)]
    if job.name_field not in fields:
        raise KeyError(
            f"field '{job.name_field}' not on '{job.index_layer}'. Available: {fields}"
        )

    taken: set[str] = set()
    pages: list[Page] = []
    oid_field = arcpy.Describe(index_layer).OIDFieldName

    with arcpy.da.SearchCursor(
        index_layer, [oid_field, job.name_field], where_clause=job.where
    ) as cursor:
        for oid, value in cursor:
            stem = render(job.name_template, {"layout": job.layout, "name": value})
            pages.append(Page(name=str(value), stem=unique(stem, taken), oid=oid))

    return pages


def export(job: Job, dry_run: bool = False) -> list[pathlib.Path]:
    """Render the series. Returns the files written (or that would be)."""
    arcpy = _arcpy()
    project, layout = open_layout(job)

    output_dir = pathlib.Path(job.output_dir)
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    pages = list_pages(job)
    frames = layout.listElements("MAPFRAME_ELEMENT")
    frame = frames[0] if frames else None
    index_layer = None
    if job.is_map_series and frame is not None:
        index_layer = {layer.name: layer for layer in frame.map.listLayers()}[job.index_layer]

    written: list[pathlib.Path] = []

    for page in pages:
        if index_layer is not None and page.oid >= 0:
            oid_field = arcpy.Describe(index_layer).OIDFieldName
            index_layer.definitionQuery = f"{oid_field} = {page.oid}"
            frame.camera.setExtent(frame.getLayerExtent(index_layer, False, True))

        for fmt in job.export.formats:
            target = output_dir / f"{page.stem}.{fmt}"
            written.append(target)

            if dry_run:
                continue
            if target.exists() and not job.overwrite:
                raise FileExistsError(
                    f"{target} already exists; set 'overwrite: true' in the job "
                    f"to replace it"
                )

            if fmt == "pdf":
                layout.exportToPDF(
                    str(target),
                    resolution=job.export.dpi,
                    georef_info=job.export.georeferenced_pdf,
                    embed_fonts=job.export.embed_fonts,
                )
            elif fmt == "png":
                layout.exportToPNG(str(target), resolution=job.export.dpi)
            elif fmt == "jpg":
                layout.exportToJPEG(str(target), resolution=job.export.dpi)
            elif fmt == "tiff":
                layout.exportToTIFF(str(target), resolution=job.export.dpi)

    if index_layer is not None:
        index_layer.definitionQuery = ""

    del project
    return written
