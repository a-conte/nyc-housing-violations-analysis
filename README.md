# NYC Housing Anomaly Analysis

[![CI](https://github.com/a-conte/nyc-housing-anomaly-analysis/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/a-conte/nyc-housing-anomaly-analysis/actions/workflows/ci.yml)

**Which New York City apartment buildings have far more serious housing violations than
similar buildings, and should get a closer look?**

When a city inspector finds a problem in an apartment building, NYC's housing agency (HPD)
issues a violation. [HPD sorts violations into three classes](https://www.nyc.gov/site/hpd/services-and-information/clear-violations.page):
Class A is non-hazardous, Class B is hazardous (such as leaks or holes in walls), and
Class C is immediately hazardous (such as no heat or hot water, lead paint, or rodents).
This project focuses on the two serious classes, B and C. It uses five years of public NYC
records (2021–2025, about 9.4 million rows) to find buildings whose violation counts are
unusually high compared with buildings of the same size, age and borough.

## The short answer

Out of **145,832 apartment buildings**, the analysis flags **27 buildings** for a closer look.

- Those 27 buildings received **11,328 serious violations in 2025**, about **420 each**. The
  average building in the study had about **4**.
- They are 0.02% of the buildings but account for **2%** of all serious violations.
- **23 of the 27** also had serious violations in every year from 2021 to 2024, so for most
  of them this was not a one-year spike.

These are **leads, not conclusions**. A high violation count shows that a building deserves a
review of its records, not that its owner broke the law. See [What this can't tell
you](#what-this-cant-tell-you).

![Left: every building in the study, with the 27 flagged buildings circled. Right: violation history for four example buildings.](reports/leads/investigative_context.png)

*Left: each shaded cell is a group of buildings; the circles are the 27 flagged buildings,
which sit well above others of the same size. Right: four example buildings, chosen by fixed
rules, show how violations climbed in 2024 and 2025.*

## How it works

### 1. Collect the data

The project downloads four public datasets from [NYC Open Data](https://opendata.cityofnewyork.us/):

| Dataset | What it contains |
| --- | --- |
| [HPD complaints](https://data.cityofnewyork.us/d/ygpa-z7cr) | Tenant complaints, like "no hot water" |
| [Housing Maintenance Code violations](https://data.cityofnewyork.us/d/wvxf-dwi5) | Violations issued by inspectors |
| [HPD buildings](https://data.cityofnewyork.us/d/kj4p-ruqc) | Each building's ID and number of apartments |
| [PLUTO](https://data.cityofnewyork.us/d/64uk-42ks) | Property details, like the year built |

The downloader checks its own work. It compares downloaded row counts with source counts
before and after downloading and stops if they differ. These checks cannot detect every
change to a live source. It also saves a fingerprint (a SHA-256
checksum) of every file, so later steps can prove they used the exact same data.

### 2. Clean and link the records

The datasets are loaded into a [DuckDB](https://duckdb.org/) database and cleaned with SQL.
Linking a violation to the right building is harder than it sounds: the city uses three
different IDs (building ID, tax lot and building number) that don't always agree. The SQL
flags detected mismatches instead of guessing. A set of 17 automatic checks must all pass before
the database is used.

### 3. Pick a fair comparison group

To compare like with like, the study keeps only buildings that:

- have at least 3 apartments and are not public housing (NYCHA),
- were built before 2021 and not majorly altered since, and
- have valid building, tax-lot and building-number IDs, with no shared active building number
  (BIN), and a matching PLUTO property record with positive residential units and area.

This leaves 145,832 buildings. Buildings with zero violations stay in, because they are part of
"normal". Shared tax lots and conflicting event IDs can still occur; they are flagged and
examined in sensitivity checks rather than treated as verified matches.

### 4. Predict how many violations each building "should" have

Bigger buildings naturally get more violations, so raw counts aren't fair. A statistical
model predicts each building's expected number of serious violations from its number of
apartments, age, borough and year. The model learns from 2021–2024 and is evaluated on 2025.
Because 2025 had already been examined during earlier model development, this is a
retrospective evaluation, not an untouched test of future performance.

Violations are very uneven: about 80% of buildings have none in a given year, while a few
have hundreds. A basic Poisson model can't handle that spread, so the project uses a
**negative binomial** model, which is designed for it.

### 5. Flag the outliers

A building is considered only if, in 2025, it had at least **10 apartments**, at least **20
serious violations**, a prediction of at least **2**, at least **10 more than predicted**, and at
least **twice** its prediction.
From those 3,934 buildings, the project takes the top 10 in each of three lists:

1. most serious violations in total,
2. most serious violations per apartment, and
3. most surprising compared with the model's prediction.

Some buildings appear on more than one list. Combined, the lists contain **27 buildings**.
There is no secret combined score; every building's reason for selection is listed in
[indicator_queues.csv](reports/leads/indicator_queues.csv).

## Is the result reliable?

**Aggregate fit improved, but the screening accuracy is unvalidated.** Across all buildings,
actual 2025 violations were 93% of what the model predicted, and 98.4% of buildings fell
inside its nominal 95% count intervals. These are useful overall diagnostics; they do not
establish that the model reliably identifies unusually high counts or useful investigative
leads. The intervals also condition on the fitted model and omit uncertainty in its
parameters, record linkage and apartment counts.

**It struggles with history.** Buildings with a long record of violations got about 2.6 times
more than predicted, and buildings with no history got far fewer. A building's past matters
more than size and age alone can capture.

**Sensitivity depends on which assumption changes.** Restricting the eligible population
can change the list substantially. Changing the apartment-count source within the same
comparable population has a smaller effect:

| Scenario | Comparison list | Leads retained | Total scenario leads |
| --- | --- | --- | --- |
| Exclude ambiguous links, including shared active HPD tax lots | Original 27 leads | 23 of 27 | 27 |
| Restrict to comparable one-building/one-lot properties, keeping HPD apartment counts | Original 27 leads | 21 of 27 | 26 |
| Within that same comparable population, switch rate and apartment-size gates to PLUTO counts | 26 comparable-population HPD leads | 25 of 26 | 26 |
| Restrict to comparable properties where HPD and PLUTO apartment counts agree | Original 27 leads | 16 of 27 | 23 |

The **25-of-26** result is not retention of the original 27 leads. All scenarios keep the
model's expected counts and residuals fixed; the PLUTO switch tests rate-based selection,
not a refitted model. Queues are replenished after each restriction, so scenarios can add
new leads. See the [full sensitivity analysis](reports/leads/README.md#selection-sensitivity-without-changing-the-model).

## What this can't tell you

- **Violations measure recorded inspection findings, not just conditions.** The analysis
  does not measure how often each building was inspected. Differences in reporting and
  inspection activity can affect the counts, so buildings where tenants report less may
  look better than they are.
- **The apartment counts are today's.** A building's size in 2021 may have been different.
- **The selection rules were chosen after seeing 2025.** They keep the list to a reviewable
  size; they are not proven cutoffs.
- **Linking records is imperfect.** Some violations may be attached to the wrong building.
- **Lead usefulness has not been established by manual source-record review.** Automated
  checks reconcile the outputs to the retained data; they do not establish how many leads
  would warrant further investigation.

Before anyone acted on these results, each building's records and identity would need to be
checked by hand. This analysis does not show wrongdoing, ongoing defects or what caused them.

## Future work

- **Account for inspection effort.** Find a measure of how often each building was
  inspected, so the model can tell bad conditions apart from frequent inspections.
- **Add a second model that uses each building's history.** The current model leaves past
  violations out on purpose, so that buildings with long records aren't treated as
  "expected" to be bad. A second model that includes history, using training years only,
  would separate buildings that are worse than their peers from buildings that are worse
  than their own past.
- **Look at owners, carefully.** HPD's public building registrations list owners and
  managing agents. Grouping buildings that share them could reveal patterns across a whole
  portfolio, but it would need careful record matching and manual checks before any name
  was attached to a finding.
- **Test other dates.** Rerun with each violation's approval date instead of its inspection
  date, since 400 violations have an approval date before their inspection date.
- **Refresh regularly.** Re-download the data on a schedule and track how the list of
  flagged buildings changes over time.

## Technical summary

**ETL (Python + DuckDB SQL)**

- Extracts from the Socrata API with keyset pagination by primary key, so pages can't
  shift while the live data changes. Retries with backoff, and shrinks the page size
  after a timeout.
- Downloads in partitions that can resume after an interruption. Each partition is
  reconciled against the source row count before and after the download, and recorded
  in a manifest with a SHA-256 checksum.
- Before loading, verifies each file against its manifest: checksum, size, header and
  readable gzip data.
- Loads every column as text, then casts types explicitly in SQL so identifiers are
  never misread as decimals.
- Builds the database in a temporary file and replaces the real one only if all 17
  blocking integrity checks pass. These include unique IDs, joins that never duplicate
  events, and event totals that match from raw tables through to the final panel.
- Links records across BuildingID, BBL and BIN with conflict flags instead of silently
  dropping mismatches.

**Analysis (Python: statsmodels, SciPy)**

- Building-year panel with log(apartments) as the exposure offset. Controls for size,
  age, borough and year trend.
- Poisson baseline, replaced by negative binomial (NB2) after the training data showed
  overdispersion (Pearson dispersion 33.37).
- Model chosen by rolling validation (2021–22 → 2023, 2021–23 → 2024). The winner adds
  piecewise size terms with knots at 10 and 50 apartments. It is refit on 2021–2024 and
  evaluated retrospectively on 2025, which had already been inspected in the baseline
  analysis. Model selection uses the earlier folds; 2025 is not an untouched holdout.
- Diagnostics: calibration by size, borough and history; 95% count-interval coverage;
  and a 300-replicate bootstrap that resamples tax lots.
- Leads come from three separate top-10 lists (count, rate, Pearson residual) instead
  of a composite score. Sensitivity checks cover ID linkage and the apartment-count source.

## Guide to the code

**ETL**

| Step | Where to look |
| --- | --- |
| Download and verify data | [housing/download.py](housing/download.py), [housing/sources.py](housing/sources.py) |
| Load into DuckDB and clean | [housing/database.py](housing/database.py), [sql/01_staging.sql](sql/01_staging.sql) |
| Link records across IDs | [sql/02_linkage.sql](sql/02_linkage.sql) |
| Build monthly and yearly counts | [sql/03_metrics.sql](sql/03_metrics.sql) |
| Run integrity and quality checks | [sql/04_audits.sql](sql/04_audits.sql), [sql/05_quality.sql](sql/05_quality.sql) |
| Build the comparison group and features | [sql/cohort/features.sql](sql/cohort/features.sql), [housing/cohort.py](housing/cohort.py) |

**Analysis**

| Step | Where to look |
| --- | --- |
| Fit and test the models | [housing/baseline_models.py](housing/baseline_models.py), [housing/model_validation.py](housing/model_validation.py) |
| Select the 27 buildings | [housing/leads.py](housing/leads.py) |

Tests for both parts are in [tests/](tests/).

The [reports/](reports/) folder holds the saved results of each stage, in the order the work
was done:

| Folder | What's inside |
| --- | --- |
| [data_quality](reports/data_quality/QUALITY_REVIEW.md) | Checks on the raw data, and what was fixed or excluded |
| [cohort](reports/cohort/README.md) | How the comparison group was chosen |
| [baseline_models](reports/baseline_models/README.md) | First models and exploratory charts |
| [model_validation](reports/model_validation/README.md) | How the final model was chosen and how well it fits |
| [leads](reports/leads/README.md) | The 27 flagged buildings, in full detail |
| [publication_review](reports/publication_review/VERIFICATION.md) | Final checks before publishing |

Inside the reports, the stages are called Phase 2 through Phase 7.

The full design reasoning is in [docs/analytical_design.md](docs/analytical_design.md).

## Run it yourself

You need Python 3.11+ and [uv](https://docs.astral.sh/uv/). You can run the tests without
downloading any NYC data:

```sh
uv sync --locked
uv run python -m pytest -q
```

A public checkout runs **40 tests and skips four** that require retained local analytical
outputs. All 44 run when those inputs are present. These checks exercise synthetic examples
and saved artifacts; they do not refit the published full-data models.

Exact reproduction of the headline numbers requires the original snapshot or matching
derived inputs, which are not distributed here. Downloading today's public records creates
a new snapshot and may produce different results. For a focused reviewer walkthrough and
full rebuild instructions (several GB of disk space), see [docs/reproduction.md](docs/reproduction.md).

## Privacy

The output files identify buildings only by HPD's public building ID. They contain no
addresses, apartment numbers, owner names or tenant information.

This is an independent portfolio project, not an investigation by any government agency.
Code is released under the [MIT License](LICENSE). NYC data is subject to
NYC Open Data's terms of use.
