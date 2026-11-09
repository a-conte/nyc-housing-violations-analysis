"""Reconcile saved Phase 6 artifacts; never rebuild data or fit a model."""

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from housing.download import sha256
from housing.leads import PLAN, choose, overlap, peer_summary
from housing.leads_report import write_report
from housing.model_validation import matrix

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/leads"


@pytest.fixture(scope="module")
def outputs():
    database = ROOT / "data/housing.duckdb"
    snapshot = ROOT / "data/leads/all_buildings_2025.csv.gz"
    if not database.exists() or not snapshot.exists():
        pytest.skip("Local analytical database and Phase 6 snapshot required")
    d = pd.read_csv(snapshot, dtype={"building_id": str})
    with duckdb.connect(str(database), read_only=True) as c:
        annual = c.sql("SELECT * FROM analytical.annual ORDER BY building_id,year").df()
        features = c.sql("SELECT * FROM analytical.features ORDER BY building_id").df()
        # Independent reconciliation to individual enforcement records.
        counts = c.sql("""
            SELECT building_id, year(event_month) AS year,
                   count(DISTINCT violation_id) FILTER (WHERE violation_class='B') AS class_b,
                   count(DISTINCT violation_id) FILTER (WHERE violation_class='C') AS class_c
            FROM clean.violations WHERE in_study GROUP BY ALL
        """).df()
    return d, annual, features, counts


def read(name):
    return pd.read_csv(REPORT / name, dtype={"building_id": str})


def equal(a, b):
    cols = list(a.columns)
    pd.testing.assert_frame_equal(
        a.fillna(np.nan).sort_values("building_id").reset_index(drop=True),
        b[cols].fillna(np.nan).sort_values("building_id").reset_index(drop=True),
        check_dtype=False,
        rtol=1e-10,
        atol=1e-10,
    )


def test_saved_cohort_and_frozen_model(outputs):
    d, annual, features, counts = outputs
    current = annual[annual.year == 2025]
    cols = [c for c in current if c in d]
    equal(current[cols], d)
    cols = [c for c in features if c in d and (c not in annual or c == "building_id")]
    equal(features[cols], d)
    joined = annual.merge(counts, on=["building_id", "year"], how="left", suffixes=("", "_raw"))
    for col in ["class_b", "class_c"]:
        np.testing.assert_array_equal(joined[col], joined[f"{col}_raw"].fillna(0))
    np.testing.assert_array_equal(annual.hazardous, annual.class_b + annual.class_c)
    assert d.building_id.is_unique and d.source_coverage_present.all()
    assert (d.calendar_months == 12).all()
    pred = pd.read_csv(
        ROOT / "data/model_validation/nb_size_2025.csv.gz", dtype={"building_id": str}
    )
    cols = [
        "building_id",
        "hazardous",
        "expected",
        "oe",
        "pearson_residual",
        "observed_minus_expected",
    ]
    equal(pred[cols], d)
    params = json.loads((ROOT / "reports/model_validation/parameters.json").read_text())["nb_size"]
    mu = np.exp(matrix(d, "nb_size", 2024) @ np.array(params["coefficients"])) * d.selected_units
    np.testing.assert_allclose(mu, d.expected, rtol=1e-10)
    np.testing.assert_allclose(d.oe, d.hazardous / mu)
    np.testing.assert_allclose(d.observed_minus_expected, d.hazardous - mu, atol=1e-10)
    np.testing.assert_allclose(
        d.pearson_residual, (d.hazardous - mu) / np.sqrt(mu + params["alpha"] * mu**2)
    )
    np.testing.assert_allclose(d.rate, 100 * d.hazardous / d.selected_units)


def test_leads_history_profiles_and_summary(outputs):
    d, annual, _, _ = outputs
    leads = read("leads.csv")
    selected, queues, eligible = choose(d)
    equal(selected, leads)
    pd.testing.assert_frame_equal(queues, read("indicator_queues.csv"), check_dtype=False)
    history = read("lead_history.csv")
    expected = annual[annual.building_id.isin(leads.building_id)][history.columns]
    pd.testing.assert_frame_equal(history, expected.reset_index(drop=True), check_dtype=False)
    prior = history[history.year < 2025].groupby("building_id").hazardous
    assert prior.size().eq(4).all()
    np.testing.assert_array_equal(leads.years_with_bc, prior.apply(lambda x: (x > 0).sum()))
    np.testing.assert_array_equal(leads.historical_bc, prior.sum())
    peers = pd.DataFrame([peer_summary(d, row) for row in leads.itertuples(index=False)])
    equal(peers, leads)
    ids = []
    for metric in PLAN["indicators"]:
        remaining = leads[~leads.building_id.isin(ids)].assign(
            numeric_id=lambda x: x.building_id.astype(int)
        )
        ids.append(
            remaining.sort_values([metric, "numeric_id"], ascending=[False, True])
            .iloc[0]
            .building_id
        )
    remaining = leads[
        ~leads.building_id.isin(ids)
        & ((leads.unit_comparison != "agreement") | leads.ambiguous_linkage)
    ]
    ids.append(remaining.sort_values("hazardous", ascending=False).iloc[0].building_id)
    equal(read("profiles.csv"), leads[leads.building_id.isin(ids)])
    s = json.loads((REPORT / "summary.json").read_text())
    assert s == {
        "cohort_buildings": len(d),
        "cohort_bc": int(d.hazardous.sum()),
        "screen_eligible": eligible,
        "leads": len(leads),
        "lead_bc": int(leads.hazardous.sum()),
        "lead_complaints": int(leads.complaints.sum()),
        "lead_problem_rows": int(leads.problems.sum()),
        "leads_with_geography_flags": int((leads.geography_flagged_events > 0).sum()),
        "leads_with_unit_disagreement": int(leads.denominator_disagrees.sum()),
        "leads_with_bc_all_prior_years": int((leads.years_with_bc == 4).sum()),
    }
    assert (s["leads"], s["lead_bc"], s["leads_with_bc_all_prior_years"]) == (27, 11328, 23)


def test_sensitivity_membership(outputs):
    d, _, _, _ = outputs
    subsets = {"primary": choose(d)[0], "clean": choose(d, allowed=~d.ambiguous_linkage)[0]}
    comparable = d[d.unit_counts_comparable & d.pluto_units.gt(0)]
    subsets["comparable_hpd"] = choose(comparable)[0]
    subsets["comparable_pluto"] = choose(comparable, "pluto_units")[0]
    subsets["agreement"] = choose(d, allowed=d.unit_comparison.eq("agreement"))[0]
    membership = read("selection_membership.csv")
    assert set(membership.building_id) == set().union(
        *(set(x.building_id) for x in subsets.values())
    )
    for name, selected in subsets.items():
        assert set(membership.loc[membership[name], "building_id"]) == set(selected.building_id)
    pairs = [
        ("primary", "clean"),
        ("primary", "comparable_hpd"),
        ("comparable_hpd", "comparable_pluto"),
        ("primary", "agreement"),
    ]
    for row, (base, other) in zip(read("sensitivity.csv").to_dict("records"), pairs, strict=True):
        row.pop("scenario")
        assert row == pytest.approx(overlap(subsets[base], subsets[other]))


def test_report_and_provenance(tmp_path):
    s = json.loads((REPORT / "summary.json").read_text())
    write_report(tmp_path, s, read("profiles.csv"), read("sensitivity.csv"))
    assert (tmp_path / "README.md").read_text() == (REPORT / "README.md").read_text()
    assert json.loads((REPORT / "selection_plan.json").read_text()) == PLAN
    provenance = json.loads((REPORT / "provenance.json").read_text())
    for key, path in {
        "code_sha256": "housing/leads.py",
        "report_code_sha256": "housing/leads_report.py",
        "plan_sha256": "reports/leads/selection_plan.json",
        "phase5_parameters_sha256": "reports/model_validation/parameters.json",
        "phase5_decision_sha256": "reports/model_validation/decision.json",
        "phase5_predictions_sha256": "data/model_validation/nb_size_2025.csv.gz",
    }.items():
        if (ROOT / path).exists():
            assert provenance[key] == sha256(ROOT / path)


def test_quality_flags_and_complaint_counts(outputs):
    d, annual, _, _ = outputs
    with duckdb.connect(str(ROOT / "data/housing.duckdb"), read_only=True) as c:
        complaints = c.sql("""
            SELECT building_id, year(event_month) AS year,
                   count(DISTINCT complaint_id) AS complaints_raw,
                   count(DISTINCT problem_id) AS problems_raw
            FROM clean.complaints WHERE in_study GROUP BY ALL
        """).df()
        quality = c.sql("""
            SELECT building_id,
                count(*) FILTER (WHERE bbl_conflict OR bin_conflict OR
                    component_bbl_conflict OR source_bbl_conflict) AS geography_flagged_events,
                count(*) FILTER (WHERE year(event_month)=2025 AND (bbl_conflict OR
                    bin_conflict OR component_bbl_conflict OR source_bbl_conflict))
                    AS geography_flagged_2025
            FROM audit.event_links WHERE in_study GROUP BY building_id
        """).df()
        dates = c.sql("""
            SELECT building_id, count(*) AS bad_approval_dates FROM clean.violations
            WHERE in_study AND approved_at < inspected_at GROUP BY building_id
        """).df()
        reporting = c.sql("""
            SELECT building_id,
                count(*) FILTER (WHERE duplicate_flag='Y') AS duplicate_flagged_problems_2025,
                count(DISTINCT received_at::DATE) AS complaint_reporting_days_2025
            FROM clean.complaints WHERE in_study AND year(event_month)=2025 GROUP BY building_id
        """).df()
    joined = annual.merge(complaints, on=["building_id", "year"], how="left")
    for col in ["complaints", "problems"]:
        np.testing.assert_array_equal(joined[col], joined[f"{col}_raw"].fillna(0))
    for source in [quality, dates, reporting]:
        expected = d[["building_id"]].merge(source, on="building_id", how="left").fillna(0)
        equal(expected, d)
    np.testing.assert_array_equal(
        d.ambiguous_linkage,
        d.geography_flagged_events.gt(0)
        | d.active_bin_records.gt(1)
        | d.active_hpd_buildings_on_lot.gt(1),
    )
    np.testing.assert_array_equal(
        d.denominator_disagrees, d.unit_counts_comparable & d.selected_units.ne(d.pluto_units)
    )
