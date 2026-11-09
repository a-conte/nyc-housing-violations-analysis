# Setup and reproduction

Run all commands from the repository root. Python 3.11+ is required; the published run used
Python 3.14. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) using its official
installation instructions, then:

```sh
uv sync --locked
uv run python -m housing --help
uv run python -m pytest -q
uv run python -m ruff check .
uv run python -m ruff format --check .
uv run python scripts/check_docs.py
```

`uv sync` includes the development group (pytest and Ruff). There is no database server,
cloud credential or application configuration step. Dependency installation requires network
access unless packages are cached. Do not copy a virtual environment between checkout paths;
move the copied `.venv` aside before recreating it with `uv sync --locked` (sync alone may
reuse it). Invoke tools as `uv run python -m ...` to avoid stale
launcher shebangs in a moved environment.

## What can be reproduced from Git alone?

The source, configuration, dependency lock, lightweight reports, figures and frozen model
coefficients are versioned. Raw snapshots, the database, full predictions and the Phase 6
cohort export are deliberately excluded. A public checkout runs 40 tests and skips four
local-data integration tests; the retained working dataset runs all 44. The tests include
small synthetic fits, not a refit of the published full-data models.

Read [the report](../reports/phase6/README.md) without installing anything. To check its saved
Markdown/provenance and synthetic selection rules specifically:

```sh
uv run python -m pytest tests/test_phase6.py tests/test_phase6_outputs.py -q
```

Exact numerical reproduction needs the original local `data/snapshot/`, including repair
manifests, or its derived database and matching predictions. Those files are not downloadable
from this repository. A fresh NYC Open Data extraction is a new snapshot: records, statuses,
reference attributes and even schema can change. Do not promise identical numbers from it.
Report renderers contain snapshot-specific interpretive prose; review narratives as well as
computed tables after any fresh-source rebuild. Historical verification records describe the
published run and are not automatically renewed by a pipeline rerun.

## Full rebuild from live sources

This path downloads data and fits models; it is not needed to review the portfolio and was
not executed during Phase 7. Run in a separate checkout or preserve the published artifacts
first: commands overwrite generated phase reports and local analytical outputs.

```sh
uv run python -m housing run
uv run python -m housing.phase3
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run python -m housing.phase4
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run python -m housing.phase5
uv run python -m housing.phase6
uv run python -m pytest -q
```

Execution order and side effects:

| Command | Required input | Output and behavior |
| --- | --- | --- |
| `housing run` | Public API access; `config.toml` | Downloads/reuses `data/snapshot`, validates it, builds `data/housing.duckdb`, writes `reports/phase2` |
| `housing.phase3` | Phase 2 database and provenance | Replaces the analytical schema transactionally; writes `reports/phase3` |
| `housing.phase4` | Phase 3 analytical tables | Fits baseline/sensitivity models; writes `data/phase4` and `reports/phase4` |
| `housing.phase5` | Phase 3 tables and Phase 4 code | Fits rolling comparisons and final models; writes `data/phase5`, coefficients, decision and reports |
| `housing.phase6` | Phase 3 tables, Phase 5 decision/parameters and `data/phase5/nb_size_2025.csv.gz` | Checks frozen predictions, writes lead outputs and `data/phase6`; does not fit models |

Phase 5 reuses Phase 4 fitting code, not its saved model predictions. Phase 4 is included
above to reproduce the full baseline report. Phases 3–6 use fixed paths and a 2021–2025
analytical contract; changing the CLI study window does not automatically adapt those phases.

The optional `SOCRATA_APP_TOKEN` environment variable is read directly by the downloader.
It is not required or written to manifests. `.env` files are ignored but are not automatically
loaded. Do not place credentials in code, configuration or reports.

## Existing local snapshot or analytical outputs

To rebuild the database without network requests, use the loader rather than `run`:

```sh
uv run python -m housing load --snapshot data/snapshot
uv run python -m housing.phase3
```

Loading verifies selection, metadata, byte counts, hashes, gzip decompression and row counts.
It builds a temporary database and replaces the destination only after blocking checks pass.
Loading removes the previous derived analytical schema by replacing the database, hence the
Phase 3 step. It does not rebuild Phase 4–6 artifacts; do not mix new inputs with old outputs.

If the retained database and matching Phase 5 predictions already exist, verify them without
rewriting any report or refitting:

```sh
uv run python -m pytest tests/test_phase6_outputs.py -q
```

To deliberately regenerate Phase 6 from those matching inputs:

```sh
uv run python -m housing.phase6
```

For a separate live extraction, both acquisition and loading accept explicit paths:

```sh
uv run python -m housing download --snapshot data/new-snapshot
uv run python -m housing load --snapshot data/new-snapshot
```

The loader still defaults to `data/housing.duckdb` and `reports/phase2`. The Phase 2 CLI also
accepts `--config`, `--database` and `--report-dir`; later runners do not accept those options.
Do not pass `--help` to a phase runner: unlike the acquisition CLI, those modules have no
argument parser and will execute their work.

## Resources, resumability and limits

[config.toml](../config.toml) sets 2021–2025, 50,000-row API pages, three download workers,
a 120-second read timeout, four request attempts, four DuckDB threads and a 4 GB DuckDB
memory limit. Completed partitions are reusable; failed downloads can be resumed with the
same command. A completed snapshot is checksum-verified and reused, not silently refreshed.
Use a new snapshot directory for changed study selection or live refresh. Corrupted complete
snapshots fail verification; preserve evidence and use a new directory rather than bypassing checks.

The retained extraction contains 9.44 million source rows across 14 partitions, including two
empty undated extracts. Compressed sources occupy about 187 MiB and DuckDB about 921 MiB on
the reviewed machine. Allow several GB of disk for snapshots, repair evidence, temporary
database replacement and model outputs. Python model arrays consume memory beyond DuckDB's
4 GB limit. Full runs require substantial network and numerical computation; runtime was
not benchmarked and depends on throttling, hardware and source revisions. The BLAS settings
above limit thread oversubscription; they do not guarantee identical floating-point results
across platforms. Timestamps and compressed-file bytes can also differ across regenerations.

The [Phase 7 verification record](../reports/phase7/VERIFICATION.md) distinguishes commands
actually run from code-path inspection and historical validation. No full-data refitting or
live-source download was performed for that review.
