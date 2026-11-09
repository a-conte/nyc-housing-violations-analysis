"""Select buildings for closer review, using the frozen Phase 5 model's 2025 predictions.

Run with `python -m housing.leads`. Applies the screening gates in PLAN, takes the top ten
buildings separately by raw count, rate and residual, and writes lead tables, sensitivity
checks and the Phase 6 report. It never refits a model.
"""

import json
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from housing.database import PROJECT
from housing.download import now, sha256
from housing.model_validation import matrix

PLAN = {
    "year": 2025,
    "minimum_apartments": 10,
    "minimum_bc": 20,
    "minimum_expected": 2,
    "minimum_excess": 10,
    "minimum_oe": 2,
    "per_indicator_limit": 10,
    "indicators": ["hazardous", "rate", "pearson_residual"],
    "tie_break": "numeric BuildingID ascending",
    "peer_rule": "same borough, 0.5–2 times HPD units, exclude target; minimum 30",
    "profiles": "highest raw count; highest rate among remaining leads; highest residual among remaining leads; highest raw count among remaining denominator/linkage-flagged leads",
}


def choose(frame, units="selected_units", allowed=None):
    d = frame.copy()
    d["rate"] = 100 * d.hazardous / d[units]
    ok = (
        (d[units] >= PLAN["minimum_apartments"])
        & (d.hazardous >= PLAN["minimum_bc"])
        & (d.expected >= PLAN["minimum_expected"])
        & (d.observed_minus_expected >= PLAN["minimum_excess"])
        & (d.oe >= PLAN["minimum_oe"])
    )
    if allowed is not None:
        ok &= allowed
    d = d[ok].copy()
    d["_id"] = d.building_id.astype("int64")
    queues = []
    for metric in PLAN["indicators"]:
        q = (
            d.sort_values([metric, "_id"], ascending=[False, True])
            .head(PLAN["per_indicator_limit"])[["building_id", metric]]
            .copy()
        )
        q["indicator"] = metric
        q["queue_position"] = np.arange(1, len(q) + 1)
        q = q.rename(columns={metric: "indicator_value"})
        queues.append(q)
    reasons = pd.concat(queues, ignore_index=True)
    ids = set(reasons.building_id)
    return (
        d[d.building_id.isin(ids)].drop(columns="_id").sort_values("building_id"),
        reasons,
        int(ok.sum()),
    )


def peer_summary(d, lead):
    peers = d[
        (d.borough_id == lead.borough_id)
        & d.selected_units.between(lead.selected_units * 0.5, lead.selected_units * 2)
        & (d.building_id != lead.building_id)
    ]
    result = {
        "building_id": lead.building_id,
        "peer_n": len(peers),
        "peer_sufficient": len(peers) >= 30,
    }
    for col in ["hazardous", "rate", "complaints"]:
        result[f"peer_{col}_median"] = float(peers[col].median()) if len(peers) >= 30 else None
        result[f"peer_{col}_p90"] = float(peers[col].quantile(0.9)) if len(peers) >= 30 else None
        result[f"peer_{col}_percentile"] = (
            float((peers[col] < getattr(lead, col)).mean() * 100) if len(peers) >= 30 else None
        )
    return result


def overlap(base, other):
    a = set(base.building_id)
    b = set(other.building_id)
    return {
        "base_leads": len(a),
        "scenario_leads": len(b),
        "retained": len(a & b),
        "removed": len(a - b),
        "added": len(b - a),
        "jaccard": len(a & b) / len(a | b) if a | b else 1.0,
    }


def main():
    report = PROJECT / "reports/leads"
    report.mkdir(parents=True, exist_ok=True)
    local = PROJECT / "data/leads"
    local.mkdir(exist_ok=True)
    (report / "selection_plan.json").write_text(json.dumps(PLAN, indent=2) + "\n")
    decision = json.loads((PROJECT / "reports/model_validation/decision.json").read_text())
    if decision["selected"] != "nb_size":
        raise ValueError("Unexpected frozen model")
    parameter_path = PROJECT / "reports/model_validation/parameters.json"
    original_hash = sha256(parameter_path)
    parameters = json.loads(parameter_path.read_text())["nb_size"]
    predictions_path = PROJECT / "data/model_validation/nb_size_2025.csv.gz"
    pred = pd.read_csv(predictions_path, dtype={"building_id": str, "bbl": str})
    with duckdb.connect(str(PROJECT / "data/housing.duckdb"), read_only=True) as c:
        annual = c.sql("""
            SELECT building_id, year, complaints, problems, class_b, class_c, hazardous,
                   calendar_months, source_coverage_present
            FROM analytical.annual
            ORDER BY building_id, year
        """).df()
        features = c.sql("""
            SELECT building_id, borough_id, selected_units, pluto_units, buildings_on_lot,
                   unit_counts_comparable, unit_comparison, year_built, building_class,
                   active_bin_records, active_hpd_buildings_on_lot, conflicting_events
            FROM analytical.features
        """).df()
        quality = c.sql("""
            SELECT building_id,
                   count(*) FILTER (WHERE bbl_conflict OR bin_conflict
                                    OR component_bbl_conflict OR source_bbl_conflict)
                       AS geography_flagged_events,
                   count(*) FILTER (WHERE year(event_month) = 2025
                                    AND (bbl_conflict OR bin_conflict
                                         OR component_bbl_conflict OR source_bbl_conflict))
                       AS geography_flagged_2025
            FROM audit.event_links
            WHERE in_study
            GROUP BY building_id
        """).df()
        dates = c.sql("""
            SELECT building_id, count(*) AS bad_approval_dates
            FROM clean.violations
            WHERE in_study AND approved_at < inspected_at
            GROUP BY building_id
        """).df()
        complaints = c.sql("""
            SELECT building_id,
                   count(*) FILTER (WHERE duplicate_flag = 'Y') AS duplicate_flagged_problems_2025,
                   count(DISTINCT received_at::DATE) AS complaint_reporting_days_2025
            FROM clean.complaints
            WHERE in_study AND year(event_month) = 2025
            GROUP BY building_id
        """).df()
    current = annual[annual.year == 2025].merge(features, on="building_id", validate="one_to_one")
    if not current.source_coverage_present.all() or not (current.calendar_months == 12).all():
        raise ValueError("Unavailable observation time")
    if set(pred.building_id) != set(current.building_id) or pred.building_id.duplicated().any():
        raise ValueError("Prediction cohort mismatch")
    d = current.merge(
        pred[
            [
                "building_id",
                "hazardous",
                "expected",
                "oe",
                "pearson_residual",
                "observed_minus_expected",
            ]
        ],
        on="building_id",
        suffixes=("", "_saved"),
        validate="one_to_one",
    )
    np.testing.assert_array_equal(d.hazardous, d.hazardous_saved)
    mu = (
        np.exp(matrix(d, "nb_size", 2024) @ np.array(parameters["coefficients"])) * d.selected_units
    )
    np.testing.assert_allclose(mu, d.expected, rtol=1e-10)
    np.testing.assert_allclose(d.oe * d.expected, d.hazardous)
    np.testing.assert_allclose(
        d.pearson_residual,
        (d.hazardous - d.expected) / np.sqrt(d.expected + parameters["alpha"] * d.expected**2),
    )
    d = d.drop(columns="hazardous_saved")
    for table in [quality, dates, complaints]:
        d = d.merge(table, on="building_id", how="left", validate="one_to_one")
    flags = [
        "geography_flagged_events",
        "geography_flagged_2025",
        "bad_approval_dates",
        "duplicate_flagged_problems_2025",
        "complaint_reporting_days_2025",
    ]
    d[flags] = d[flags].fillna(0).astype(int)
    history = (
        annual[annual.year < 2025]
        .groupby("building_id")
        .agg(
            historical_bc=("hazardous", "sum"),
            years_with_bc=("hazardous", lambda x: (x > 0).sum()),
            years_with_20plus_bc=("hazardous", lambda x: (x >= 20).sum()),
            historical_complaints=("complaints", "sum"),
            historical_problems=("problems", "sum"),
        )
        .reset_index()
    )
    d = d.merge(history, on="building_id", validate="one_to_one")
    d["rate"] = 100 * d.hazardous / d.selected_units
    d["denominator_disagrees"] = d.unit_counts_comparable & (d.selected_units != d.pluto_units)
    d["ambiguous_linkage"] = (
        (d.geography_flagged_events > 0)
        | (d.active_bin_records > 1)
        | (d.active_hpd_buildings_on_lot > 1)
    )
    leads, queues, eligible = choose(d)
    peers = pd.DataFrame([peer_summary(d, row) for row in leads.itertuples(index=False)])
    leads = leads.merge(peers, on="building_id", validate="one_to_one")
    leads["selection_indicators"] = leads.building_id.map(
        queues.groupby("building_id").indicator.agg(", ".join)
    )
    leads.to_csv(report / "leads.csv", index=False)
    queues.to_csv(report / "indicator_queues.csv", index=False)
    annual[annual.building_id.isin(leads.building_id)].to_csv(
        report / "lead_history.csv", index=False
    )
    d.to_csv(local / "all_buildings_2025.csv.gz", index=False)
    clean, _, _ = choose(d, allowed=~d.ambiguous_linkage)
    comparable = d[d.unit_counts_comparable & d.pluto_units.notna() & (d.pluto_units > 0)].copy()
    hpd, _, _ = choose(comparable)
    pluto, _, _ = choose(comparable, "pluto_units")
    agreement, _, _ = choose(d, allowed=d.unit_comparison.eq("agreement"))
    scenarios = [
        ("exclude_ambiguous", leads, clean),
        ("comparable_HPD_vs_full", leads, hpd),
        ("comparable_PLUTO_vs_HPD", hpd, pluto),
        ("agreement_only", leads, agreement),
    ]
    sensitivity = pd.DataFrame(
        [{"scenario": label, **overlap(base, other)} for label, base, other in scenarios]
    )
    sensitivity.to_csv(report / "sensitivity.csv", index=False)
    membership = d[["building_id"]].copy()
    for name, subset in [
        ("primary", leads),
        ("clean", clean),
        ("comparable_hpd", hpd),
        ("comparable_pluto", pluto),
        ("agreement", agreement),
    ]:
        membership[name] = membership.building_id.isin(subset.building_id)
    membership[membership.drop(columns="building_id").any(axis=1)].to_csv(
        report / "selection_membership.csv", index=False
    )
    profile_ids = []
    for metric in PLAN["indicators"]:
        remaining = leads[~leads.building_id.isin(profile_ids)].copy()
        remaining["_id"] = remaining.building_id.astype("int64")
        if len(remaining):
            profile_ids.append(
                remaining.sort_values([metric, "_id"], ascending=[False, True]).iloc[0].building_id
            )
    review = leads[
        ~leads.building_id.isin(profile_ids)
        & ((leads.unit_comparison != "agreement") | leads.ambiguous_linkage)
    ].copy()
    review["_id"] = review.building_id.astype("int64")
    if len(review):
        profile_ids.append(
            review.sort_values(["hazardous", "_id"], ascending=[False, True]).iloc[0].building_id
        )
    profiles = leads[leads.building_id.isin(profile_ids)].copy()
    profiles.to_csv(report / "profiles.csv", index=False)
    fig, axs = plt.subplots(1, 2, figsize=(11, 4))
    axs[0].hexbin(
        np.log1p(d.selected_units),
        np.log1p(d.hazardous),
        gridsize=40,
        bins="log",
        mincnt=1,
        cmap="Greys",
    )
    axs[0].scatter(
        np.log1p(leads.selected_units),
        np.log1p(leads.hazardous),
        facecolors="none",
        edgecolors="#c45227",
        label="Exploratory leads",
    )
    axs[0].set(
        xlabel="log(1 + apartments)", ylabel="log(1 + B/C)", title="2025 cohort and selected leads"
    )
    axs[0].legend()
    for key in profile_ids:
        a = annual[annual.building_id == key]
        axs[1].plot(a.year, a.hazardous, "o-", label=f"BuildingID {key}")
    axs[1].axvline(2024.5, color="grey", linestyle="--")
    axs[1].set(
        xticks=range(2021, 2026),
        xlabel="Year",
        ylabel="Recorded B/C violations",
        title="Illustrative profiles: history and 2025",
    )
    axs[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(report / "investigative_context.png", dpi=150)
    plt.close(fig)
    summary = {
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
    (report / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (report / "provenance.json").write_text(
        json.dumps(
            {
                "generated_at": now(),
                "code_sha256": sha256(Path(__file__)),
                "report_code_sha256": sha256(PROJECT / "housing/leads_report.py"),
                "plan_sha256": sha256(report / "selection_plan.json"),
                "phase5_parameters_sha256": original_hash,
                "phase5_predictions_sha256": sha256(predictions_path),
                "phase5_decision_sha256": sha256(
                    PROJECT / "reports/model_validation/decision.json"
                ),
            },
            indent=2,
        )
        + "\n"
    )
    assert original_hash == sha256(parameter_path)
    from housing.leads_report import write_report

    write_report(report, summary, profiles, sensitivity)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
