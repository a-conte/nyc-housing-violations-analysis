-- Analytical cohort and building-level features.
-- Rebuilt by `python -m housing.cohort`; replaces only tables in the analytical schema.

CREATE SCHEMA IF NOT EXISTS analytical;

-- Every HPD building gets the first eligibility rule it fails (1-7), or 8 if it passes all.
CREATE OR REPLACE TABLE analytical.eligibility AS
WITH bins AS (
    SELECT bin, count(*) AS n
    FROM clean.buildings
    WHERE record_status = 'ACTIVE' AND lifecycle = 'BUILDING' AND bin IS NOT NULL
    GROUP BY bin
), conflicts AS (
    SELECT building_id,
           count(*) FILTER (WHERE bbl_conflict OR bin_conflict OR component_bbl_conflict)
               AS conflicting_events
    FROM audit.event_links
    WHERE in_study
    GROUP BY building_id
)
SELECT b.*,
       coalesce(n, 0) AS active_bin_records,
       coalesce(conflicting_events, 0) AS conflicting_events,
       CASE
           WHEN building_id IS NULL OR bbl IS NULL OR bin IS NULL THEN 1
           WHEN NOT candidate_multifamily THEN 2
           WHEN NOT pluto_matched
                OR pluto_units IS NULL OR pluto_units <= 0
                OR residential_area IS NULL OR residential_area <= 0 THEN 3
           WHEN n > 1 THEN 4
           WHEN year_built IS NULL OR year_built >= year(start_date) THEN 5
           WHEN (year_altered_1 >= year(start_date) OR year_altered_2 >= year(start_date)) THEN 6
           WHEN NOT (SELECT bool_and(complaints_present AND violations_present)
                     FROM mart.source_months) THEN 7
           ELSE 8
       END AS eligibility_step,
       hpd_units AS selected_units,
       unit_comparison = 'agreement' AS agreement_sensitivity,
       coalesce(conflicting_events, 0) = 0 AS clean_linkage_sensitivity
FROM mart.buildings b
LEFT JOIN bins USING (bin)
LEFT JOIN conflicts USING (building_id)
CROSS JOIN run_config;

-- One row per eligible building per year, with rates per 100 apartment-years.
CREATE OR REPLACE TABLE analytical.annual AS
SELECT y.*,
       e.selected_units,
       e.agreement_sensitivity,
       e.clean_linkage_sensitivity,
       e.selected_units * y.calendar_months / 12.0 AS capacity_unit_years,
       100.0 * y.complaints / (e.selected_units * y.calendar_months / 12.0)
           AS complaints_per_100_unit_years,
       100.0 * y.class_b / (e.selected_units * y.calendar_months / 12.0)
           AS class_b_per_100_unit_years,
       100.0 * y.class_c / (e.selected_units * y.calendar_months / 12.0)
           AS class_c_per_100_unit_years
FROM mart.building_year y
JOIN analytical.eligibility e USING (building_id)
WHERE eligibility_step = 8;

-- One row per eligible building: study-period totals, persistence and rates.
CREATE OR REPLACE TABLE analytical.features AS
WITH totals AS (
    SELECT building_id,
           sum(complaints) AS complaints,
           sum(problems) AS problems,
           sum(class_b) AS class_b,
           sum(class_c) AS class_c,
           sum(hazardous) AS hazardous,
           count(*) AS observed_years,
           sum(capacity_unit_years) AS capacity_unit_years,
           count(*) FILTER (WHERE complaints > 0) AS years_with_complaints,
           count(*) FILTER (WHERE hazardous > 0) AS years_with_hazardous,
           sum(months_with_complaints) AS months_with_complaints,
           sum(months_with_hazardous) AS months_with_hazardous
    FROM analytical.annual
    GROUP BY building_id
)
SELECT e.*,
       t.* EXCLUDE (building_id),
       100.0 * complaints / capacity_unit_years AS complaints_per_100_unit_years,
       100.0 * class_b / capacity_unit_years AS class_b_per_100_unit_years,
       100.0 * class_c / capacity_unit_years AS class_c_per_100_unit_years,
       100.0 * hazardous / capacity_unit_years AS hazardous_per_100_unit_years
FROM analytical.eligibility e
JOIN totals t USING (building_id);

-- How many buildings and events each eligibility rule removes.
CREATE OR REPLACE TABLE analytical.exclusions AS
WITH activity AS (
    SELECT building_id,
           sum(complaints) AS complaints,
           sum(class_b) AS class_b,
           sum(class_c) AS class_c
    FROM mart.building_year
    GROUP BY building_id
)
SELECT eligibility_step,
       count(*) AS buildings,
       sum(complaints) AS complaints,
       sum(class_b) AS class_b,
       sum(class_c) AS class_c
FROM analytical.eligibility
LEFT JOIN activity USING (building_id)
GROUP BY eligibility_step;

-- Compares HPD and PLUTO unit counts for candidate buildings, by borough, class and size.
CREATE OR REPLACE TABLE analytical.denominator_review AS
WITH activity AS (
    SELECT building_id,
           sum(complaints) AS complaints,
           sum(hazardous) AS hazardous
    FROM mart.building_year
    GROUP BY building_id
)
SELECT borough_id,
       building_class,
       unit_comparison,
       CASE WHEN hpd_units < 10 THEN '3-9'
            WHEN hpd_units < 50 THEN '10-49'
            ELSE '50+' END AS size_band,
       count(*) AS buildings,
       count(rate_units) AS phase2_denominators,
       median(hpd_units) AS median_hpd_units,
       median(pluto_units) AS median_lot_units,
       median(unit_relative_difference) AS median_comparable_relative_difference,
       sum(complaints) AS complaints,
       sum(hazardous) AS hazardous
FROM mart.buildings
JOIN activity USING (building_id)
WHERE candidate_multifamily
GROUP BY ALL;
