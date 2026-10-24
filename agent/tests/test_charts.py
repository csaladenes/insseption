"""Offline tests for TEMPO response parsing and selection helpers (canned fixtures, no network)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from charts import (  # noqa: E402
    _is_county_option,
    apply_single_year,
    build_chart,
    choose_kind,
    expand_county_selections,
    extract_series,
    mentioned_years,
    parse_number,
    parse_year_range,
    prefer_matrix_for_years,
    relative_year_range,
    select_named_counties,
)

DIMS = ["Sexe", "Macroregiuni, regiuni de dezvoltare si judete", "Ani"]


def tall(rows: list[tuple[str, str]], year: str = "Anul 2025") -> dict:
    """Single-year TEMPO response: three header rows, then one row per territory."""
    return {
        "columns": DIMS,
        "rows": [
            [DIMS[0], DIMS[1], year],
            [DIMS[0], DIMS[1], "UM: Numar"],
            [DIMS[0], DIMS[1], "Numar"],
            *[["Total", label, value] for label, value in rows],
        ],
    }


def wide(rows: list[tuple[str, list[str]]], years: list[int]) -> dict:
    """Multi-year TEMPO response: years as columns."""
    ycols = [f"Anul {y}" for y in years]
    return {
        "columns": [DIMS[0], DIMS[1], *["Ani"] * len(years)],
        "rows": [
            [DIMS[0], DIMS[1], *ycols],
            [DIMS[0], DIMS[1], *["UM: Numar"] * len(years)],
            [DIMS[0], DIMS[1], *["Numar"] * len(years)],
            *[["Total", label, *vals] for label, vals in rows],
        ],
    }


META = {
    "dimensions": [
        {"dim_code": 1, "label": "Sexe", "options": [
            {"label": "Total ", "nom_item_id": 105}, {"label": "Masculin ", "nom_item_id": 106}]},
        {"dim_code": 2, "label": "Macroregiuni, regiuni de dezvoltare si judete", "options": [
            {"label": "TOTAL", "nom_item_id": 112},
            {"label": "MACROREGIUNEA UNU", "nom_item_id": 113},
            {"label": "Regiunea NORD-VEST", "nom_item_id": 114},
            {"label": "Bihor", "nom_item_id": 115},
            {"label": "Cluj", "nom_item_id": 116},
            {"label": "Olt", "nom_item_id": 117},
            {"label": "Regiunea BUCURESTI - ILFOV", "nom_item_id": 118},
            {"label": "Municipiul Bucuresti", "nom_item_id": 119},
            {"label": "Timis", "nom_item_id": 120}]},
        {"dim_code": 3, "label": "Ani", "options": [
            {"label": f"Anul {y}", "nom_item_id": 4000 + y} for y in range(1995, 2026)]},
    ]
}


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("19041322", 19041322.0),
        ("<u>19041322</u>", 19041322.0),
        ("<strong>706585</strong>", 706585.0),
        ("171.451,2", 171451.2),
        ("3,2", 3.2),
        ("skipLine", None),
        (None, None),
    ],
)
def test_parse_number(raw, expected):
    assert parse_number(raw) == expected


def test_county_values_in_year_band_are_kept():
    # Values in 1900-2100 next to a value >= 10000 used to be dropped as "years".
    data = tall([("Municipiul Bucuresti", "22936"), ("Alba", "2087"), ("Olt", "2039"), ("Harghita", "1966")])
    labels, values, _ = extract_series(data)
    assert labels == ["Municipiul Bucuresti", "Alba", "Olt", "Harghita"]
    assert values == [22936.0, 2087.0, 2039.0, 1966.0]


def test_header_and_marker_rows_are_skipped():
    data = tall([("Bihor", "<u>575731</u>"), ("xxx", "skipLine")])
    labels, values, _ = extract_series(data)
    assert labels == ["Bihor"] and values == [575731.0]


def test_wide_single_row_is_a_time_series_even_for_small_values():
    data = wide([("TOTAL", ["5,0", "4,8", "4,0"])], [2015, 2016, 2017])
    labels, values, _ = extract_series(data)
    assert labels == ["2015", "2016", "2017"] and values == [5.0, 4.8, 4.0]


def test_wide_multi_row_keeps_every_territory_and_full_table():
    data = wide(
        [("Bihor", ["xxx", "575731", "<strong>572057</strong>"]), ("Timis", ["xxx", "685821", "695760"])],
        [2005, 2012, 2015],
    )
    labels, values, _ = extract_series(data)
    assert labels == ["Bihor", "Timis"] and values == [572057.0, 695760.0]
    _, table = build_chart("Populația pe județe între 2005 și 2015", data)
    assert table["columns"] == [DIMS[1], "2005", "2012", "2015"]
    assert table["rows"][0] == ["Bihor", None, 575731.0, 572057.0]


@pytest.mark.parametrize(
    "query, labels, kind",
    [
        ("Live births 2010-2020", ["2010", "2011", "2012"], "line"),
        ("Population by county 2005-2015", [f"c{i}" for i in range(42)], "map"),
        ("Cluj and Timis 2010-2020", ["Cluj", "Timis"], "bar"),
    ],
)
def test_choose_kind(query, labels, kind):
    assert choose_kind(query, labels, [1.0] * len(labels)) == kind


COUNTIES = tall([(f"County {i}", str(1000 + i)) for i in range(42)])


@pytest.mark.parametrize(
    "query, hint, kind",
    [
        ("Népesség megyénként 2020-ban", "bar", "choropleth"),  # planner hint can't override shape
        ("Hospital beds by county", "line", "choropleth"),
        ("Population by county as a bar chart", "map", "bar"),  # explicit request wins
        ("Population of Romania by area", "bar", "bar"),  # no signal: hint decides
    ],
)
def test_chart_kind_precedence(query, hint, kind):
    chart, _ = build_chart(query, COUNTIES, hint=hint)
    assert (chart.get("type") if chart.get("type") == "choropleth" else chart.get("kind")) == kind


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Population in 2020", None),
        ("in 2020\nin 2020", None),  # same year repeated is not a range
        ("between 1995 and 2020", (1995, 2020)),
        ("1990-2000", (1990, 2000)),
    ],
)
def test_parse_year_range(text, expected):
    assert parse_year_range(text) == expected


def test_mentioned_years_single():
    assert mentioned_years("Population of Romania in 1995") == (1995, 1995)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Emigranți definitivi în ultimii 10 ani", (2016, 2025)),
        ("Inflation over the last 5 years", (2021, 2025)),
        ("az elmúlt 3 évben", (2023, 2025)),
        ("Population now", None),
    ],
)
def test_relative_year_range(text, expected):
    assert relative_year_range(text, META) == expected


def test_romanian_region_labels_are_not_counties():
    assert not _is_county_option("Regiunea NORD-VEST")
    assert not _is_county_option("MACROREGIUNEA UNU")
    assert not _is_county_option("TOTAL")
    assert _is_county_option("Bihor")


def test_expand_counties_keeps_chosen_year():
    sel = expand_county_selections(META, {"3": [4000 + 2020]})
    assert sel["2"] == [115, 116, 117, 119, 120]
    assert sel["3"] == [4000 + 2020]


def test_expand_counties_defaults_to_latest_year():
    assert expand_county_selections(META, {})["3"] == [4000 + 2025]


def test_apply_single_year_drops_non_dim_keys():
    sel = apply_single_year(META, {"year": [1], "1": [105]}, 1995)
    assert sel == {"1": [105], "3": [4000 + 1995]}


@pytest.mark.parametrize(
    "query, ids",
    [
        ("Compare the population of Cluj and Timiș", [116, 120]),
        ("Care este populația Bucureștiului?", [119]),
        ("Kolozs megye lakossága", [116]),
        ("Sud-Vest Oltenia earnings", None),  # 'Olt' must not match 'Oltenia'
        ("Population of Romania", None),
    ],
)
def test_select_named_counties(query, ids):
    sel = select_named_counties(META, {}, query)
    assert (sel or {}).get("2") == ids if ids else sel is None


def test_prefer_matrix_for_years_only_swaps_population():
    assert prefer_matrix_for_years("1995", "POP105A", years=(1995, 1995)) == "POP107A"
    assert prefer_matrix_for_years("1985", "POP105A", years=(1985, 1985)) == "POP111A"
    assert prefer_matrix_for_years("1995", "IPC101A", years=(1995, 2000)) == "IPC101A"
    assert not prefer_matrix_for_years("cars in 1995", "", years=(1995, 1995))
