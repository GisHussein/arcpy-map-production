"""Command line interface.

    mapseries validate jobs/districts.yml    # the spec alone, no ArcGIS needed
    mapseries check    jobs/districts.yml    # pre-flight the layout (needs Pro)
    mapseries names    jobs/districts.yml    # what the files will be called
    mapseries run      jobs/districts.yml    # export

``validate`` and ``names --preview`` run anywhere. The rest need the ArcGIS Pro
Python environment.
"""

from __future__ import annotations

import argparse
import sys

from .job import Job, JobError
from .naming import render, unique
from .qa import summarise


def _load(path: str) -> Job:
    try:
        return Job.load(path)
    except (JobError, OSError) as exc:
        print(f"mapseries: {exc}", file=sys.stderr)
        raise SystemExit(2)


def cmd_validate(args) -> int:
    job = _load(args.job)
    print(f"project       : {job.project}")
    print(f"layout        : {job.layout}")
    print(f"output        : {job.output_dir}")
    print(f"mode          : {'map series' if job.is_map_series else 'single layout'}")
    if job.is_map_series:
        print(f"index layer   : {job.index_layer} ({job.name_field})")
        if job.where:
            print(f"where         : {job.where}")
    print(f"formats       : {', '.join(job.export.formats)} at {job.export.dpi} dpi")
    print(f"name template : {job.name_template}")
    print("\nspec is valid")
    return 0


def cmd_names(args) -> int:
    job = _load(args.job)

    if args.preview:
        taken: set[str] = set()
        print("preview (no ArcGIS needed):")
        for value in args.preview:
            stem = render(job.name_template, {"layout": job.layout, "name": value})
            print(f"  {value!r:32} -> {unique(stem, taken)}.{job.export.formats[0]}")
        return 0

    from .arcgis import list_pages

    pages = list_pages(job)
    for page in pages:
        print(f"{page.name} -> {page.stem}")
    print(f"\n{len(pages)} page(s)")
    return 0


def cmd_check(args) -> int:
    job = _load(args.job)
    from .arcgis import inspect_layout

    issues = inspect_layout(job)
    for issue in issues:
        mark = "FAIL" if issue.severity == "error" else "WARN"
        print(f"[{mark}] {issue.code}: {issue.message}")

    errors, warnings = summarise(issues)
    if not issues:
        print("layout is ready")
    else:
        print(f"\n{errors} error(s), {warnings} warning(s)")
    return 1 if errors else 0


def cmd_run(args) -> int:
    job = _load(args.job)
    from .arcgis import export, inspect_layout

    if not args.skip_checks:
        issues = inspect_layout(job)
        errors, _ = summarise(issues)
        if errors:
            for issue in issues:
                if issue.severity == "error":
                    print(f"[FAIL] {issue.code}: {issue.message}")
            print("\nrefusing to export a layout that fails pre-flight; "
                  "pass --skip-checks to override")
            return 1

    written = export(job, dry_run=args.dry_run)
    verb = "would write" if args.dry_run else "wrote"
    for path in written:
        print(f"{verb} {path}")
    print(f"\n{len(written)} file(s)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mapseries", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="check the job spec alone")
    p.add_argument("job")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("names", help="show the output file names")
    p.add_argument("job")
    p.add_argument(
        "--preview",
        nargs="+",
        metavar="VALUE",
        help="try the template on these values without opening the project",
    )
    p.set_defaults(func=cmd_names)

    p = sub.add_parser("check", help="pre-flight the layout")
    p.add_argument("job")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("run", help="export the map series")
    p.add_argument("job")
    p.add_argument("--dry-run", action="store_true", help="list the files, export nothing")
    p.add_argument("--skip-checks", action="store_true", help="export even if pre-flight fails")
    p.set_defaults(func=cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (RuntimeError, KeyError, FileNotFoundError, FileExistsError) as exc:
        print(f"mapseries: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
