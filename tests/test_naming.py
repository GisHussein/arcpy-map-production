import pytest

from mapseries.naming import MAX_STEM, render, slugify, unique


@pytest.mark.parametrize(
    "value,expected",
    [
        ("Marsa Alam", "Marsa_Alam"),
        ("  Ras   Banas  ", "Ras_Banas"),
        ("Wadi El-Gemal", "Wadi_El-Gemal"),
        ("Zone 3/4", "Zone_3_4"),
        (r"North\South", "North_South"),
        ("Quseir: Sheet 1", "Quseir_Sheet_1"),
        ("sheet<1>", "sheet_1"),
        ("Hurghada\nNorth", "Hurghada_North"),
        (42, "42"),
        ("__leading__", "leading"),
    ],
)
def test_slugify_makes_a_safe_stem(value, expected):
    assert slugify(value) == expected


def test_slugify_handles_empty_and_null():
    assert slugify(None) == "unnamed"
    assert slugify("") == "unnamed"
    assert slugify("   ") == "unnamed"
    assert slugify("***", fallback="sheet") == "sheet"


def test_slugify_transliterates_accents():
    assert slugify("Béni Suef") == "Beni_Suef"


def test_non_latin_falls_back_rather_than_producing_an_empty_name():
    # An Arabic district name has no ASCII equivalent; the point is that the
    # run continues with a usable name instead of writing ".pdf".
    assert slugify("مرسى علم", fallback="district") == "district"


def test_windows_reserved_names_are_escaped():
    assert slugify("CON") == "CON_map"
    assert slugify("com1") == "com1_map"


def test_long_names_are_truncated():
    assert len(slugify("A" * 500)) == MAX_STEM


def test_render_fills_the_template():
    assert render("{layout}_{name}", {"layout": "A3 Map", "name": "Marsa Alam"}) == (
        "A3_Map_Marsa_Alam"
    )


def test_render_rejects_an_unknown_token():
    with pytest.raises(KeyError) as exc:
        render("{layout}_{sheet}", {"layout": "A3"})
    assert "sheet" in str(exc.value)


def test_unique_disambiguates_repeated_names():
    taken: set[str] = set()
    assert unique("Al_Qusayr", taken) == "Al_Qusayr"
    assert unique("Al_Qusayr", taken) == "Al_Qusayr_2"
    assert unique("Al_Qusayr", taken) == "Al_Qusayr_3"


def test_unique_is_case_insensitive_like_windows():
    taken: set[str] = set()
    unique("Sheet_A", taken)
    assert unique("sheet_a", taken) == "sheet_a_2"
