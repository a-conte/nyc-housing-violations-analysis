"""Write the Phase 3 cohort report. Run by `python -m housing.cohort` after the build."""

import duckdb

from housing.database import PROJECT, export_csv, markdown_table

REPORT = PROJECT / "reports/cohort"

# How many buildings, complaints and violations remain after each eligibility rule.
RULE_COVERAGE = """
WITH v AS (
    SELECT building_id, count(*) AS violations
    FROM clean.violations
    WHERE in_study
    GROUP BY 1
), a AS (
    SELECT building_id, sum(complaints) AS complaints
    FROM mart.building_year
    GROUP BY 1
)
SELECT step,
       count(*) FILTER (WHERE eligibility_step >= step) AS retained_buildings,
       sum(complaints) FILTER (WHERE eligibility_step >= step) AS retained_complaints,
       100.0 * sum(complaints) FILTER (WHERE eligibility_step >= step)
           / (SELECT count(DISTINCT complaint_id) FROM clean.complaints WHERE in_study)
           AS complaint_percent,
       sum(coalesce(violations, 0)) FILTER (WHERE eligibility_step >= step)
           AS retained_violations,
       100.0 * sum(coalesce(violations, 0)) FILTER (WHERE eligibility_step >= step)
           / (SELECT count(*) FROM clean.violations WHERE in_study)
           AS violation_percent
FROM analytical.eligibility
LEFT JOIN a USING (building_id)
LEFT JOIN v USING (building_id)
CROSS JOIN range(1, 9) r(step)
GROUP BY step
ORDER BY step
"""

# Spread of HPD-vs-PLUTO apartment-count differences, by comparison category.
UNIT_DISCREPANCIES = """
SELECT unit_comparison,
       count(*) AS buildings,
       median(unit_relative_difference) AS median_relative_difference,
       quantile_cont(unit_relative_difference, 0.1) AS p10,
       quantile_cont(unit_relative_difference, 0.9) AS p90
FROM mart.buildings
WHERE candidate_multifamily
GROUP BY 1
ORDER BY 1
"""

# What made up the months whose violation counts jumped or fell sharply year over year.
SHIFT_COMPOSITION = """
WITH d AS (
    SELECT event_month,
           violation_class,
           count(*) AS n,
           count(DISTINCT building_id) AS buildings,
           count(DISTINCT order_number) AS orders,
           max(day_count) AS largest_day_rows
    FROM (
        SELECT *,
               count(*) OVER (
                   PARTITION BY event_month, violation_class, inspected_at::DATE
               ) AS day_count
        FROM clean.violations
        WHERE in_study
    )
    GROUP BY 1, 2
)
SELECT *
FROM d
WHERE event_month IN (
    SELECT event_month
    FROM audit.monthly_coverage
    WHERE source = 'violations'
      AND (year_over_year_ratio < 0.5 OR year_over_year_ratio > 2)
)
ORDER BY 1, 2
"""


def main() -> None:
    """Export the cohort review tables and write reports/cohort/README.md."""
    with duckdb.connect(str(PROJECT / "data/housing.duckdb"), read_only=True) as connection:
        export_csv(connection, RULE_COVERAGE, REPORT / "rule_coverage.csv")
        cursor = connection.execute(RULE_COVERAGE)
        table = markdown_table([column[0] for column in cursor.description], cursor.fetchall())
        export_csv(connection, UNIT_DISCREPANCIES, REPORT / "unit_discrepancies.csv")
        export_csv(connection, SHIFT_COMPOSITION, REPORT / "shift_composition.csv")
    (REPORT / "README.md").write_text(
        """# Analytical cohort and SQL features (Phase 3)

## In short

- Started from all 381,275 buildings in HPD's inventory and applied seven rules in order,
  keeping **145,832 apartment buildings** as the comparison group.
- The rules keep current buildings with at least 3 apartments that are not public housing,
  have clean IDs and a matching city property record, were built before 2021, have no
  recorded alterations since, and have complete data for every month.
- 75,106 of the kept buildings had no complaints or serious violations in five years. They
  stay in, because they are part of "normal".
- Apartment counts come from HPD. PLUTO's counts are kept only for sensitivity checks,
  because PLUTO counts apartments per tax lot, and one lot can hold several buildings.

Completed using the existing frozen inputs; no models or new source downloads.
Reproduce with `python -m housing.cohort` after Phase 2. SQL lives in
`sql/cohort/features.sql`. Rebuilds replace only the analytical schema tables inside a transaction.

## Denominator decision

The Phase 2 missing-denominator fraction (35.9%) is mostly a validation-policy exclusion:
all 152,361 candidates already have positive HPD apartment counts. Agreement retained
97,663 buildings; 26,605 disagree and 27,209 lack comparable building/lot cardinality.
The median signed relative discrepancy among comparable disagreements is +4.55%; see
unit_discrepancies.csv for dispersion, not just the median. Lot totals cannot be assigned
as building exposure. Use HPD apartments as current building capacity, without imputation.
Retain PLUTO counts and agreement_sensitivity for an independently corroborated subset.
This expands coverage but does not establish that HPD is always correct. Extreme discrepancies
need case review in Phase 4. denominator_review.csv quantifies selection jointly by borough,
size, building class and complaint/B-C activity. Phase 2 retention was 67.72% for small
buildings versus 42.24% for 50+ units, so agreement-only analysis is selectively restrictive.

## Eligibility and retained coverage

Rules are ordered; exclusions are mutually exclusive. Step 1 is the full HPD inventory;
step 2 has passed identifier validation, and step 8 has passed every rule:

1. Valid BuildingID, BBL and BIN.
2. Current active building, at least three HPD apartments, zero Class B rooms, known
   non-NYCHA management.
3. PLUTO match with positive residential units and residential area, corroborating residential use.
4. No BIN shared by multiple active HPD records. Shared lots are retained with HPD denominators.
5. Known construction year strictly before the study start; never use event occurrence as
   eligibility evidence.
6. No recorded alteration year at or after study start (a conservative history sensitivity
   restriction).
7. Both event sources present in every study month. A missing month blocks the cohort rather
   than creating zeros.

"""
        + table
        + """

The final cohort contains **145,832 buildings**, **1,961,330 complaints**, **1,445,019 B**
and **1,089,687 C** violations. **75,106 buildings** have no recorded complaints or B/C
violations across the study. Exclusion totals are in exclusions.csv; rule_coverage.csv includes
all-class violations and source-wide event shares, including events outside the current inventory.
Residential eligibility is a documented capacity proxy, not verified rental tenure; co-ops,
condominiums and mixed-use properties are not silently declared rental buildings.

## Linkage and monthly shifts

No events are rematched using BBL or BIN. Shared active BINs affected 917 candidates,
including 146 with Phase 2 denominators. These physical-building ambiguities are excluded
explicitly. Event geographic conflicts remain attached to BuildingID, counted in conflicting_events,
with clean_linkage_sensitivity available. Geographic changes, errors and lot restructuring
cannot be distinguished from these snapshots. Unmatched events stay in Phase 2 audit tables.

All eight monthly warnings involve violations. Their all-class ratios span 0.223–3.646,
but B/C ratios span 0.915–1.448. Class A/I composition accounts for much of the discrepancy;
this is compatible with administrative batches as well as changes in recorded activity and
is not evidence of a cause. shift_composition.csv adds distinct buildings, order-code diversity
and peak inspection-day counts for each flagged month/class. Compare with
../data_quality/monthly_change_review.csv; no months are deleted, adjusted or imputed.
400 approval dates precede inspection; inspection remains the event date. Date sensitivity
remains necessary.

## Feature contract and readiness

analytical.features has exactly one row per eligible BuildingID; analytical.annual has one
row per eligible building/year. These contain original characteristics, both unit sources,
selected_units, annual and total distinct complaints and problems, separate B/C counts,
months and years with activity, capacity_unit_years and rates per 100 capacity-unit-years.
Persistence means recorded activity, not statistically elevated activity. Zero means no matched
record within observed source months. No observed events are required for inclusion.

Capacity-unit-years use current HPD units multiplied by complete calendar years. Pre-study
construction and absence of recorded alterations do **not** prove stable units, continuous
occupancy, or historical eligibility. The estimand is historical recorded activity in the current
inventory with conservative history screens, not historical NYC rental housing as a whole.
The mixed November 2/5 extraction dates and mutable statuses remain limitations.

Ready for conditional descriptive modeling, not causal or misconduct conclusions. Phase 4 should
compare HPD and agreement-subset results on explicit common populations, assess large unit
discrepancies and conflict-free subsets, test pandemic/date sensitivity, and begin with a Poisson
baseline and overdispersion diagnostics. Reserve 2025 only after specifying the training design:
the five-year total/persistence fields include 2025 and must never be training predictors for it.
Use annual rows through 2024 to construct training-only features. No Phase 4 work was performed.
"""
    )


if __name__ == "__main__":
    main()
