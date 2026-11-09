# Final documentation and publication review (Phase 7)

## In short

- Final checks before the repository went public: a clean setup, the tests, lint, link checks,
  and a scan to confirm no data files or credentials were included.
- Everything passed. The last section records the November 9 cleanup (renamed files and
  folders, reformatted code), which changed no results.

Completed November 9, 2026. This phase prepared the public repository; it did not extend the
analysis, download data, refit models, commit, push or publish anything.

## Changes

- Rewrote the root README around the investigative question, verified findings, dataset grain,
  cohort, implementation, three existing figures and prominent limitations. Removed stale
  “no models fitted,” future-notebook and future-Isolation-Forest statements from the current
  project overview.
- Added [reproduction instructions](../../docs/reproduction.md) covering public-clone tests,
  retained-data checks, the full pipeline, fixed paths, overwrite behavior, resource needs,
  and the difference between reproducing a method and reproducing a frozen snapshot.
- Added a final scope note to the [original design](../../docs/analytical_design.md), preserving
  the proposal and phase history while identifying proposals that were not implemented.
- Extended `.gitignore` for local credentials, build products and temporary/editor files.
  Removed the ignored root `.DS_Store`. No substantive analysis, audit evidence or methodological
  documentation was deleted; no redundant tracked development artifacts warranted removal.
- Added [a local Markdown link checker](../../scripts/check_docs.py). It checks inline local
  links, directory targets, Markdown fragments and image paths in tracked and nonignored new
  Markdown files, excluding fenced examples. It does not query external websites.

## Validation performed

| Check | Result |
| --- | --- |
| Locked environment setup | `uv sync --locked --offline`: resolved 32 packages, audited 27 installed packages; no dependency changes |
| CLI contract | `python -m housing --help` verified command names, flags and default paths against the source |
| Full suite with retained data | `uv run --offline python -m pytest -q`: **44 passed**, no skips |
| Public-file-only copy | **40 passed, 4 skipped** using the existing interpreter against a temporary copy with no data or environment |
| Ruff lint and format | Passed across the repository |
| Local Markdown links and figures | All targets passed `python scripts/check_docs.py` |
| Snapshot verification | All 14 partitions and 9,439,989 source rows: metadata/selection contracts, byte counts, SHA-256, complete gzip decompression and recorded count reconciliation passed |
| Output reconciliation | Phase 6 tests rechecked DuckDB counts/features/flags, frozen predictions, queues, peers, profiles, sensitivity membership, report rendering and current provenance |
| Figure review | All three README images inspected; references point to existing PNGs, captions agree with the reports and CSV evidence |
| Publication inventory | No data, DuckDB, environment, credentials or temporary files in the publishable file list; all individual files below 5 MB |
| Git history size | No historical Git blob above 5 MB |
| Credential-pattern check | No private-key headers or high-signal AWS/GitHub credential patterns in publishable text; this is a bounded pattern check, not a guarantee about all possible secrets |
| Ignore rules | Representative data, environment, secret, cache and temporary paths correctly excluded |
| Whitespace | `git diff --check` passed |

The installed uv 0.9.1 initially panicked in macOS system-configuration lookup inside the
sandbox. The same dry run and actual offline sync succeeded outside it, followed by the uv
full-test command. No dependency installation was needed. The public-file-only test used the
existing interpreter and packages: it verifies behavior without private data, not a fresh
network installation or every supported Python/platform combination. Python 3.14 was tested.

Full live acquisition, database rebuilding and full-data fitting were **not** rerun. Command
ordering and side effects were verified by inspecting entry points and prior phase validation
records. Read-only snapshot and output checks reused existing files. Small synthetic model
fits within the test suite are distinct from retraining the published model.

## Consistency and provenance

The headline findings match [Phase 6 evidence](../leads/VERIFICATION.md): 27 leads, 11,328
B/C violations, 23 with B/C in every prior year, clean-linkage retention 23/27 and comparable
HPD-to-PLUTO retention 25/26. The README also distinguishes comparable-population restriction
(21/27 retained) and agreement-only selection (16/27 retained, 23 scenario leads).

Historical persistence is not a selection variable. It is also not independent corroboration,
because historical records participated in model estimation. The README clarifies that the
model choice used pre-2025 folds after Phase 4 had examined 2025; neither model development
nor the later operational thresholds establish an untouched evaluation.

Earlier phase reports are preserved as dated evidence. Phase 2's provisional agreement-only
rate subset was superseded by Phase 3's HPD-capacity policy and explicit sensitivity analysis.
Their “next phase” language and smaller historical test counts describe those phases, not
uncompleted current tasks. The final-scope note reconciles the original proposal with the
implemented project rather than rewriting the historical design.

Phase 4's `code_sha256` differs from today's helper module for a documented reason: it matches
`housing/phase4.py` at commit `2e4f380`, which generated the baseline report. Commit `d6a929f`
added optional `design_matrix` arguments to fitting/scoring for Phase 5; the default Phase 4
path remains unchanged. Phase 5's recorded `phase4_code_sha256` matches the current helper.
Current Phase 5/6 analytical code hashes, Phase 4/6 report-code hashes and recorded lock hashes
were checked. Historical provenance was not overwritten to imply a new analytical run.

## Remaining issues before publication

- Exact original-snapshot reproduction requires ignored local files; Git contains sufficient
  code and lightweight evidence to inspect the work, not the full research dataset.
  A fresh source extraction may differ, and snapshot-specific narrative in report renderers
  needs editorial review after a rebuild. Full-download runtime was not benchmarked.
- Historical exposure, property linkage, inspection/reporting opportunity, alternative event
  dates and imperfect calibration remain substantive limitations. No formal anomaly or
  wrongdoing claim is supported, and consequential use requires source-record review.
- No code license had been selected at this review; the MIT License was added on November 9,
  2026 (see below). NYC source-data terms are separate.
- External URLs were preserved as source/documentation references, not checked for live
  availability in this phase. Internal links and figure references were checked.

No unresolved local test, formatting, internal-link or publication-inventory failure remains.
Publication itself remains a maintainer action; Phase 7 stops here.

## Post-review code cleanup — November 9, 2026

Readability changes only; no analytical logic, thresholds or outputs changed.

- Modules were renamed from stage numbers to what they do: `phase3` → `cohort`,
  `phase3_review` → `cohort_report`, `phase4` → `baseline_models`, `phase4_report` →
  `baseline_report`, `phase5` → `model_validation`, `phase5_report` → `validation_report`,
  `phase6` → `leads`, `phase6_report` → `leads_report`. `sql/phase3/features.sql` moved to
  `sql/cohort/features.sql`. Tests were renamed to match.
- Report folders were renamed the same way: `phase2` → `data_quality`, `phase3` → `cohort`,
  `phase4` → `baseline_models`, `phase5` → `model_validation`, `phase6` → `leads`,
  `phase7` → `publication_review` (and the local `data/phase4–6` folders to match). Report
  titles now lead with the topic and keep the phase number in parentheses; text inside the
  reports still refers to phases, the order in which the work was done.
- `sql/cohort/features.sql` was reformatted. Run against a copy of the database, it produced the
  same columns, column order and rows (zero differences in either direction) for all five
  analytical tables. `python -m housing.cohort` was then rerun; only the cohort `provenance.json`
  changed.
- Docstrings and type hints were added to the acquisition, database and baseline-model modules;
  embedded SQL strings were reformatted; a `/tmp` Matplotlib cache override was removed.
- `python -m housing.leads` was rerun so the leads provenance records the renamed code. Every
  leads output except `provenance.json`, and the local 2025 snapshot, was byte-identical.
- Phases 4 and 5 were not refit. Their recorded code hashes describe the files under their
  old names at commit `a9c9722` and earlier, as documented above.
- The MIT License was added.
- Docstrings and type hints were added to every remaining Python function (lead selection,
  model validation, cohort build and report writers). `python -m housing.leads` was rerun;
  only its `provenance.json` changed.
- Plain-language "In short" summaries were added to the top of each stage report. Generated
  reports were regenerated from saved outputs (data quality, cohort, baseline models, leads)
  and differ only by the new section. The model-validation summary was added identically to
  its renderer and saved report, because regenerating it would require refitting.
