# Leads completion review (Phase 6) — November 9, 2026

## In short

- A review of the leads stage. Automated tests recheck every number in the leads report
  against the database and the individual violation records.
- All headline results were confirmed: 27 leads, 11,328 serious violations in 2025, and the
  sensitivity results.

Phase 6 is complete. The existing selection implementation, analytical snapshot, queues,
lead/profile/history tables, sensitivity outputs and figure were already generated when this
review resumed. They were retained. Only report wording, report provenance, repository
navigation and verification tests were finalized. A pre-existing root README code-block
formatting failure was corrected. No source downloads, database writes, model fits, Phase 5
changes, commits, pushes or Phase 7 work were performed.

## Verified results

| Claim | Reconciled result |
| --- | --- |
| Primary exploratory leads | 27 unique BuildingIDs |
| Selected 2025 B/C violations | 11,328 of 571,613 cohort B/C (1.98%) |
| Selected complaint context | 4,371 distinct complaints; 8,516 problem rows |
| B/C recorded in every prior year, 2021–2024 | 23 of 27 leads |
| Excluding ambiguous links | 23 retained, 4 removed, 4 added; 27 scenario leads |
| PLUTO versus HPD on the same comparable population | 25 retained, 1 removed, 1 added; 26 selections in each |
| Agreement-only population | 16 of 27 primary leads retained; 23 scenario leads |

The clean-linkage scenario's four removed primary leads share active HPD lots. No primary
lead has a recorded event-geography conflict. Absence of such a flag does not verify linkage.
The comparable HPD population itself retains only 21 of the 27 primary selections: this
population restriction is distinct from the 25-of-26 denominator-switch result.

## Evidence and checks

`tests/test_leads_outputs.py` reconciles saved artifacts without running the Phase 6 pipeline:

- All 145,832 current-cohort rows, exposure fields and property features against read-only
  DuckDB analytical views; annual B/C against distinct individual violation records, and
  complaint/problem counts against their distinct source identifiers.
- Frozen predictions against the saved Phase 5 output and coefficient-based expectations;
  rates, O/E, excess counts and NB2 Pearson residuals against their formulas.
- Selected IDs, queue values/positions, summary counts, all lead histories, peer summaries,
  illustrative profile membership, sensitivity overlaps and membership flags.
- Geographic, date and duplicate-report flags against DuckDB; denominator and ambiguity flags
  against their definitions.
- Generated Markdown against its report renderer; selection plan and provenance hashes
  against the unchanged analytical code and frozen model inputs.

The existing figure was visually inspected for legibility and re-rendered in a temporary
directory using the original plotting block, saved cohort/leads and DuckDB annual histories.
The rendered PNG matched the existing figure pixel for pixel; the original was preserved.
The report's Phase 5 calibration statements were checked against `final_metrics.csv`,
`final_groups.csv` and `temporal_rates.csv`: aggregate O/E 0.931613, conditional 95% coverage
0.983721, historical-stratum O/E 2.602981 (20+) and 0.145214 (zero), and rate change -0.074870.

Final checks from the repository root:

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Results: **44 tests passed**, Ruff lint passed, formatting passed. The local-data integration
tests ran without skips; they explicitly skip when the ignored analytical database/snapshot
is unavailable. The relocated virtual environment's `pytest` launcher has a stale interpreter
path; invoking pytest through `.venv/bin/python -m pytest` works and was used above.

## Interpretation and unresolved limitations

The review gates and top-ten queues are reproducible operational choices made after Phase 5
reviewed 2025, not preregistered or statistically validated anomaly thresholds. No composite
score, tail-probability claim or investigative accuracy estimate is produced.

Persistence is neither a gate nor a ranking variable. Prior records were training outcomes,
so persistence remains descriptive context rather than independent corroboration. Complaint
and violation agreement also reflects a potentially connected reporting/inspection process.

Unresolved substantive limitations are current-stock selection and historical exposure
uncertainty, shared-lot/geographic linkage ambiguity, unmeasured inspection/reporting
opportunity, mutable source records, and historical-activity/temporal model miscalibration.
Conditional count intervals do not include parameter or data-quality uncertainty. None of
these results establishes continued defects, affected households or wrongdoing. Consequential
building-level interpretation still requires source-record and exposure verification.

No unresolved Phase 6 implementation or output-consistency issue was found.
