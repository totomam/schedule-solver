# Changelog

Notable changes to the scheduler, newest first. Routine weekly data updates
(new `avail.json` / `reqoff.json` / `forecast.json` + backbone tweaks) are not logged here.

## 2026-07

### Repo structure
- **Stable input filenames.** Live inputs are now `avail.json` / `reqoff.json` / `forecast.json`
  (the week's date lives inside `forecast.json` as `week_start`). No more renaming files or
  editing filename references in the code each week. The stress-test baseline is `stress_*.json`.
- **`backbone.py` is the single source of truth.** The weekly backbone, people groups
  (`PB`, `NO_BREAK`, `FT_NONLEADER`, `TEN_HR`), the 12-hour rest rule, and per-person special
  rules all live here, imported by both `solver2.py` and `test_protocol.py` so they can't drift.

### Solver
- **11pm closers counted as 10:45 in `paid_val`.** Closers scheduled to 11pm clock out ~10:45,
  so paid hours count an 11pm end as 22.75 everywhere (incl. the weekly/daily budget band),
  giving the solver ~4h/week more clock time. Applied *on top of* the break deduction.
- **Adam's weekend make-up rule (`WEEKEND_MAKEUP` in `backbone.py`).** He's normally Mon-Fri
  only; a weekday req-off now automatically unlocks his usual 1pm-11pm pattern on Sat and/or
  Sun (whichever he hasn't also req'd off), so he can still hit his hours. No `avail.json`
  editing required — handled in `avwin()`.
- **Reilly Weakley's 3-shift cap.** Hard-capped at 3 shifts/week (`SHIFT_CAP` in `backbone.py`,
  shared with `test_protocol.py`); his `FT_NONLEADER` hour floor is overridden to 24h to match
  what 3 shifts can actually deliver.

### Stress test / CI
- **CI smoke test now actually fails** on a bad run (the harness exits non-zero; seed pinned for
  reproducibility). Previously a failed audit still left CI green.
- **Reachability math models the 12-hour rest rule** (per-day DP) instead of a naive "5 longest
  windows" sum, so it no longer over-states a person's max hours and false-flags shortfalls.
- **Fixed the 10-hour-shift list:** the prep full-timers (Michael, Molly, Noah, Reilly) leave by
  5pm and can't work 10h, so they're correctly excluded from `TEN_HR` (the test had over-counted them).
- **`SHIFT_CAP_GRID_TOLERANCE_H`:** people with a below-default `SHIFT_CAP` (currently only
  Reilly) have their achievable hours quantized in whole-shift increments, so a legitimate MIP
  near-miss can be close to a full hour rather than the generic half-hour `GRID_TOLERANCE_H` —
  a 50-run stress batch caught this misclassifying Reilly's floor as a hard failure.

### Cleanups
- Single-sourced per-person hour floors, the 12-hour rest predicate, and per-person special rules
  (Molly's 5pm cap, Bryan's 1-day cap, Adam's fixed 1pm–11pm) into named tables/helpers.
