import pathlib

import pytest

from mapseries.cli import main
from mapseries.job import ExportSettings, Job, JobError
from mapseries.qa import (
    check_required_elements,
    check_scale,
    check_text_elements,
    normalise,
    summarise,
)

JOBS = pathlib.Path(__file__).resolve().parents[1] / "jobs"

MINIMAL = {
    "project": "p.aprx",
    "layout": "A3",
    "output_dir": "out",
}


# --- job spec -------------------------------------------------------------


def test_example_job_loads():
    job = Job.load(JOBS / "districts.yml")
    assert job.layout == "A3_District_Landscape"
    assert job.is_map_series
    assert job.export.formats == ["pdf", "png"]
    assert job.export.dpi == 300


def test_required_keys():
    for key in ("project", "layout", "output_dir"):
        data = dict(MINIMAL)
        del data[key]
        with pytest.raises(JobError, match=key):
            Job.from_dict(data)


def test_unknown_key_is_rejected():
    with pytest.raises(JobError, match="layot"):
        Job.from_dict({**MINIMAL, "layot": "A3"})


def test_index_layer_and_name_field_must_come_together():
    with pytest.raises(JobError, match="together"):
        Job.from_dict({**MINIMAL, "index_layer": "Districts"})
    with pytest.raises(JobError, match="together"):
        Job.from_dict({**MINIMAL, "name_field": "NAME"})


def test_single_layout_job_is_valid():
    job = Job.from_dict(MINIMAL)
    assert not job.is_map_series


def test_unsupported_format_is_rejected():
    with pytest.raises(JobError, match="format"):
        ExportSettings(formats=["svg"])


def test_absurd_dpi_is_rejected():
    with pytest.raises(JobError, match="dpi"):
        ExportSettings(dpi=6000)


# --- layout pre-flight ----------------------------------------------------


def test_normalise_matches_loose_element_names():
    assert normalise("North Arrow") == normalise("north_arrow") == normalise("NorthArrow")


def test_missing_elements_are_errors():
    issues = check_required_elements(["Title", "Legend"])
    codes = {issue.message for issue in issues}
    assert any("scalebar" in message for message in codes)
    assert all(issue.severity == "error" for issue in issues)


def test_a_complete_layout_passes():
    present = ["Title", "Scale Bar", "North Arrow", "Legend", "Credits"]
    assert check_required_elements(present) == []


def test_custom_required_list_is_respected():
    assert check_required_elements(["Title"], required=["title"]) == []


def test_placeholder_text_is_an_error():
    issues = check_text_elements({"Title": "Text"})
    assert issues and issues[0].severity == "error"


def test_unresolved_dynamic_text_is_caught():
    issues = check_text_elements({"PageName": '<dyn type="page" property="name"/>'})
    assert issues and issues[0].code == "layout.placeholder_text"


def test_empty_text_is_a_warning():
    issues = check_text_elements({"Subtitle": "   "})
    assert issues and issues[0].severity == "warning"


def test_real_text_passes():
    assert check_text_elements({"Title": "Red Sea Governorate - District 4"}) == []


def test_round_scale_passes():
    assert check_scale(25000) == []


def test_odd_scale_is_a_warning():
    issues = check_scale(23847.2)
    assert issues and issues[0].code == "layout.odd_scale"


def test_unknown_scale_is_a_warning():
    issues = check_scale(None)
    assert issues and issues[0].code == "layout.unknown_scale"


def test_summarise_counts_by_severity():
    issues = check_required_elements(["Title"]) + check_text_elements({"T": ""})
    errors, warnings = summarise(issues)
    assert errors == 4 and warnings == 1


# --- CLI ------------------------------------------------------------------


def test_cli_validate(capsys):
    assert main(["validate", str(JOBS / "districts.yml")]) == 0
    assert "spec is valid" in capsys.readouterr().out


def test_cli_validate_reports_a_bad_spec(tmp_path, capsys):
    bad = tmp_path / "bad.yml"
    bad.write_text("layout: A3\n")
    with pytest.raises(SystemExit) as exc:
        main(["validate", str(bad)])
    assert exc.value.code == 2
    assert "project" in capsys.readouterr().err


def test_cli_name_preview_needs_no_arcgis(capsys):
    code = main(
        [
            "names",
            str(JOBS / "districts.yml"),
            "--preview",
            "Marsa Alam",
            "Al Qusayr",
            "Al Qusayr",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "A3_District_Landscape_Marsa_Alam.pdf" in out
    assert "A3_District_Landscape_Al_Qusayr_2.pdf" in out  # collision handled


def test_cli_reports_missing_arcpy_clearly(capsys):
    code = main(["check", str(JOBS / "districts.yml")])
    assert code == 2
    assert "arcpy" in capsys.readouterr().err.lower()
