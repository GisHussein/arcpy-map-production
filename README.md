# arcpy-map-production

Batch map production for ArcGIS Pro, driven by a YAML job spec — with the
pre-flight checks that stop a 400-page series from failing on page 340.

A map series is an hour of rendering. The two ways that hour gets wasted are
always the same: a layout element someone deleted in a different edit, and an
attribute value that is not a legal file name. Both are cheap to check before
the first page renders, and expensive to discover afterwards.

```bash
mapseries validate jobs/districts.yml   # the spec alone - no ArcGIS needed
mapseries names    jobs/districts.yml   # what the files will be called
mapseries check    jobs/districts.yml   # pre-flight the layout
mapseries run      jobs/districts.yml   # export
```

## The job spec

One YAML file per output, in version control, readable without opening Pro:

```yaml
project: C:/projects/red_sea_governorate/red_sea.aprx
layout: A3_District_Landscape
output_dir: C:/projects/red_sea_governorate/output/districts

index_layer: District_Boundaries
name_field: DISTRICT_NAME_EN
where: "STATUS = 'active'"

name_template: "{layout}_{name}"
overwrite: false

export:
  formats: [pdf, png]
  dpi: 300
  georeferenced_pdf: true
  embed_fonts: true

required_elements: [title, scalebar, north_arrow, legend, credits]
```

Leave out `index_layer` / `name_field` and it exports the layout once. Give one
without the other and it refuses to run rather than guessing.

## Pre-flight

`mapseries check` opens the layout and asks the questions a reviewer would:

```
[FAIL] layout.missing_element: layout has no element matching 'scalebar'
[FAIL] layout.placeholder_text: text element 'Title' still reads 'Text'
[WARN] layout.odd_scale: map frame is at 1:23,847, not one of the standard scales

2 error(s), 1 warning(s)
```

`mapseries run` runs these first and refuses to export if any of them is an
error, unless you pass `--skip-checks`. That default is the whole point: the
checks only help if they run without being remembered.

The scale check earns its place more often than it should. A map frame left on
whatever scale the last zoom produced is the clearest sign a layout was exported
without anyone looking at it.

## File names

Output names come from attribute values, and attribute values contain slashes,
colons, trailing spaces, newlines and non-Latin text. `mapseries names
--preview` tries the template on real values without opening the project:

```
$ mapseries names jobs/districts.yml --preview "Marsa Alam" "Zone 3/4" "Al Qusayr" "Al Qusayr"
  'Marsa Alam'  -> A3_District_Landscape_Marsa_Alam.pdf
  'Zone 3/4'    -> A3_District_Landscape_Zone_3_4.pdf
  'Al Qusayr'   -> A3_District_Landscape_Al_Qusayr.pdf
  'Al Qusayr'   -> A3_District_Landscape_Al_Qusayr_2.pdf
```

Two districts with the same name in one index layer is normal. The second one
silently overwriting the first is not — so duplicates get a suffix rather than a
race. Accents are transliterated (`Béni Suef` → `Beni_Suef`), Windows reserved
names are escaped (`CON` → `CON_map`), and a value with no ASCII equivalent at
all falls back to a usable stem instead of producing `.pdf`.

## Install

Inside the ArcGIS Pro Python environment (Pro → Python → `arcgispro-py3`):

```bash
pip install -e .
```

The spec, naming and QA modules need nothing but `PyYAML`, so `validate` and
`names --preview` run on any machine.

## How it is laid out

| Module | Needs ArcGIS | What it does |
|---|---|---|
| `mapseries/job.py` | no | load and validate the job spec |
| `mapseries/naming.py` | no | attribute value → safe, unique file name |
| `mapseries/qa.py` | no | the pre-flight rules, over plain lists and strings |
| `mapseries/cli.py` | partly | the commands |
| `mapseries/arcgis.py` | **yes** | every `arcpy` call in the package |

`arcpy` is imported lazily and only in `arcgis.py`. That split is deliberate:
it keeps the rules reviewable and testable on a machine without a licence, and
it means a missing licence produces one clear message rather than an
`ImportError` on line 1.

## Tests

```bash
pytest
```

42 tests, none of which need ArcGIS Pro — they cover the spec loader, the
naming rules (including the Windows reserved names, the collision handling and
the non-Latin fallback), every pre-flight rule, and the CLI.

**What is not tested:** `mapseries/arcgis.py`. There is no honest way to
unit-test an `arcpy` call without `arcpy`; a mocked version would only assert
that the mock was called. That module is exercised manually against ArcGIS Pro
3.x, and it is kept small and boring for exactly that reason. The tests do
cover the case where `arcpy` is missing, so the failure is a sentence rather
than a stack trace.

## Licence

MIT.
