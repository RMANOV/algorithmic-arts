# CHITIN prediction correctness Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development; independently review each contract and the integrated candidate.

**Goal:** Correct demonstrated forecast, contact-identity, calibration and native endurance measurement defects without rewarding a preferred strategy.

**Architecture:** Keep the delivered single-file runtime and its utility/score weights. Add a bounded lifetime projection shared by long forecasts and short model validation; retain long outcomes as descriptive measurements. Correct contact selection and integrate GUI active time at real transitions.

**Tech Stack:** Python 3.10+, standard library, Tk, unittest, Windows subprocesses.

**Spec:** User-provided CHITIN 2.0 skeptical audit; independently executed witnesses under `Downloads/chitin-concept-audit-20261026` and native GUI witness under `Downloads/algorithmic-arts-audit-20261026/gui_skeptic`.

## Global constraints

- Original delivered runtime SHA256: d57be0a19290030f8c8f22147bc95af706311167efa72a323583b494f1f15112; baseline commit 5696491.
- Separate candidate worktree; original running Windows endurance process and screensaver remain untouched.
- No added dependencies, hidden information, RNG draws in projection, policy bonuses or selected winning seeds.
- Heavy work runs BelowNormal; individual test subprocess timeout at most 120 seconds.
- Native Git worktree API cannot select this separate repository from the task's home directory; use external Downloads worktree.
- Global Git formatter modified the first local baseline commit; restored original bytes and amended before any implementation. Disable that hook per commit, not globally.

## Review focus

- Preserve pre-death yield while preventing post-death effects and expenditure beyond available energy.
- RAID score and motion must refer to the same contact, while frozen remote command coordinates stay frozen.
- Short predictions are validated before a new choice/cost; death remains evidence, not a filtered failure.
- Long outcomes remain visible despite replanning and never masquerade as clean model calibration.
- Pausing and resuming between probes, hidden windows and sleep must not manufacture endurance completion.

## Task 1: Lifetime accounting

Files: `CHITIN/battle_evolution.py` projection helpers/body; `tests/test_chitin_lifetime.py`.

- [x] Reproduce baseline failure with an explicit phase: pre-step H1/E0 dies after 2.2 ore; post-metabolism/pre-action H1/E0 can still earn 2.75 including the current action. Neither can earn 15; energy expenditure must be zero.
- [x] Bound accumulation by actual projected life and energy; retain healthy 15-ore control, late-death yields and absorbing death.
- [x] Expose chosen-action short projection points through `validation_candidates` without adding their value to scores.
- [x] Run regression controls and measure bounded overhead against the original.

## Task 2: RAID contact identity

Files: `CHITIN/battle_evolution.py::predictive_target`; `tests/test_chitin_raid.py`.

- [x] Reproduce nearest-neighbor trail changing the stationary rich target and actual movement (2 expected RED failures).
- [x] Use selected RAID contact consistently; preserve missing-target fallback and command coordinate guard.
- [x] Verify unrelated motion invariance, same-contact motion response, ATTACK/FLANK and remote command controls (7 PASS).

## Task 3: Calibration semantics

Files: `ForecastLedger`, decision hooks and trust lookup in runtime; `tests/test_chitin_calibration.py`.

- [x] Add failing contract tests for replanning contamination, genuine short error, early death, BUILD and epoch censoring.
- [x] Freeze short projection until next decision without changing RNG order; settle before next planning cost/action change.
- [x] Keep long outcomes, label interventions, exclude their mixed error from model trust.
- [x] Retain existing trust formula/score scale; no automatic epoch forgiveness.

## Task 4: Native endurance measurement

Files: GUI transition handlers and `SoakRecorder`; `tests/test_chitin_soak.py`.

- [x] Replay pause/resume between one-second probes; establish original false completion (3 expected RED failures).
- [x] Invalidate mixed intervals at pause/visibility/reset transitions; preserve continuous run accumulation and long-gap exclusion (7 PASS, independent review GO).
- [x] Verify native witness cannot finish before required active time; fail reports remain failures.

## Integration and delivery

- [x] Run all new regressions, embedded self-check and existing repository tests in bounded subprocesses.
- [x] Run fixed headless seeds 7001-7003, 3000 ticks each; report invariants and cost, not a selected winner.
- [x] Independent skeptical review and targeted graph/contract follow-up; resolve blocking findings.
- [x] Update model version/docs and manifest; package candidate with exact hashes and test receipts.
- [x] Verify native candidate separately; original endurance evidence does not accept a changed hash.

## Explicitly deferred

Full branching planner, entire terrain/hazard rollout, genealogy/fitness redesign, independent world RNG streams and categorical strategy dominance are outside this fix: they require a separately specified experiment and are not necessary to close the four demonstrated contracts. Visible-terrain forecast discrepancy remains a documented model limitation, not a claimed correction. Command target inertia remains a note because no harm was measured.

## Completion evidence

See `docs/reviews/2026-10-26-chitin-fix-report-bg.md`. All four contracts closed. Relevant38 regressions and17 embedded checks pass; existing32 tests passed separately. Combined collection interrupted in unchanged old GUI test and explicitly NOT claimed PASS. Native candidate accepted for short checks; new8h endurance remains running, not accepted.
