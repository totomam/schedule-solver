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
- **Convex within-tier fairness penalty for strong/reg/weak hours floors.** The old flat linear
  penalty had no preference for how a fixed tier-wide shortfall got distributed, so one person
  could absorb an entire tier's shortfall (found via Logan Frias: 7h under while regular_PT
  tier-mates sat 1-2h under, despite having far more real reachable capacity than his target).
  `_sh_floor(..., convex=True)` now splits shortfall into a cheap tranche (first `floor/3`
  hours, normal tier weight) and an expensive tranche (`_HPEN_STRONG_HI`=505/`_HPEN_REG_HI`=199/
  `_HPEN_WEAK_HI`=149, each sandwiched to preserve the leader>ft>strong>reg>weak ordering) via a
  new `_sh_tiered()` helper — spreading a fixed shortfall is always cheaper than concentrating
  it once the expensive tranche kicks in. `leader`/`ft` stay on the simple linear `_sh` since
  their weight gap to the tier above is too tight to split safely. Confirmed: regular_PT's
  spread tightened from one person at 7h short next to others at 1-2h, to everyone landing
  within 1.5h of each other.
- **Harper Flynn moved into `weak5`** (was `regular_PT`, 12h target) — her 2 available days
  give a true ceiling of 9h, which the day-count-only reachability gate didn't catch (same class
  of bug as Jacob/Jonathan's moves last entry, caught while investigating Logan's shortfall).
- **`HoursUnder` audit now suppresses shortfalls within `grid_tolerance()`.** Moved
  `GRID_TOLERANCE_H`(0.5h)/`SHIFT_CAP_GRID_TOLERANCE_H`(1.5h) from `test_protocol.py` into
  `backbone.py` as a shared `grid_tolerance(person)` helper, and applied it in `solver2.py`'s own
  live audit (previously only a 0.01h floating-point epsilon) so ordinary MIP/gapRel imprecision
  (e.g. Trinity Stringer's frequent ~0.5h misses) no longer prints as a `HoursUnder` issue at all
  — matching what the stress-test classifier already treated as a non-failure. Real shortfalls
  above tolerance are unaffected.
- **Removed Gracelyn Dailey's 30h `_FLOOR` override** — she now uses the standard `strong_PT` 18h
  target like the rest of that group.
- **Jacob Cothern and Jonathan Beacham moved into `weak5`** (were `regular_PT`, 12h target) — now
  a 4h target with the group's 2-day/week cap and "prefer one day" treatment. Jacob's separate
  2-shift `SHIFT_CAP` entry in `backbone.py` was removed as redundant (weak5's own default 2-day
  cap already matched it); his custom 10h `_FLOOR` override was also removed since 4h is well
  within his real ceiling and needs no special-casing anymore.
- **Lowered hours-floor targets: FT non-leader 33h→30h, strong PT 20h→18h.** Tested empirically
  against a heavy req-off week (~919h nominal demand vs. a ~740h paid-hours budget ceiling — a
  structural gap that exists every week): the moderate cut eliminated more than half the flagged
  `HoursUnder` shortfall with zero coverage-quality tradeoffs, vs. a more aggressive cut (28h/15h)
  that started breaking the Friday closer end-time staggering target. Regular PT stays at 12h
  (already matched the target level).
- **Zac Duffy moved into `FT_NONLEADER`** (was a standalone `_sh_floor()` call with the same
  `ft`-tier weight) — keeps his own 30h `_FLOOR` override, same pattern as Adam (40h) and Reilly
  (24h) within the group. Removed the now-redundant duplicate call in `solver2.py`.
- **Jacob Cothern moved into `regular_PT`** (was ungrouped, no hours target at all) — keeps his
  own 10h `_FLOOR` override since his 2-shift cap + ~5h dinner-only window (Mon-Thu 5p-9:30p)
  puts his true ceiling below the group's 12h floor, same pattern as Reilly's 24h override.
- **Adam Van Bogaert's standard shift changed to 2pm-11pm (was 1pm-11pm)** — 9h/day instead of
  10h. Removed the now-unused `EXTRA_SHIFTS` dead-zone seed (14:00 is a normal anchor-grid start,
  unlike 13:00); updated `WEEKEND_MAKEUP` to match; his exact-40h floor gate needed
  `ceil(40/9)=5` available days instead of 4 (tuned for the old 10h shift) to avoid a latent
  infeasibility at exactly 4 available days.
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
- **Hours-floor reachable fallback.** Previously, when someone's availability shrank below the
  days needed for their full weekly floor (e.g. a heavy req-off week), most groups just dropped
  the hour-floor incentive entirely — found via Ava Shade: 1 available day, no floor pressure at
  all, left at the 4h minimum shift instead of the 10h her one day could support. `_sh_floor()`
  now falls back to pushing toward the actual achievable ceiling (`_reachable_hours()`) instead
  of giving up, generalizing the fallback Jay/Myles/James/Adam already had individually.
- **5-tier hours-floor priority cascade.** Replaced the old 2-tier HI/LO split with
  `leader(520) > ft(510) > strong(200) > reg(150) > weak(100)`, matching the existing role
  hierarchy, so when multiple people compete for the same scarce leftover hours, the
  harder-working tiers fill first.
- **Sunday's dinner hard floor raised to 11** (was 10, now matches Thursday's 11) — human
  preference for Sunday reliably hitting 11 over Thursday reaching a 12th body. A soft-weight
  nudge was tried first (up to 5000, larger than every other soft penalty including
  `_TRIO_ESCAPE`) but HiGHS's time-limited search didn't reliably find the improvement even
  though it's provably free; promoted to a hard floor instead, same reliability fix already
  applied to the PB opener/closer floors.
- **Closer target unified to 5 every day, with a large penalty for sitting at 4.** Removed the
  Fri/Sat/Sun bump to 6 (`Ctar` now uniform `[5,5,5,5,5,5,5]`); renamed `_CLOSE_SMALL`(300) to
  `_CLOSE_PEN`(900) — human preference for 4 closers to be rare, not a routine thin-day outcome.
  Weighted between `_LUNCHPEN`(800) and `_TRIO_ESCAPE`(1000).
- **Dinner redefined: starts ≤6pm AND ends ≥8pm** (was just "ends after 5pm") — per human
  request, so "working dinner" means actually covering the dinner rush, not just a late-afternoon
  departure. Accepted tradeoff: Fri/Sat's floor of 13 now has ~zero slack (even a fully-staffed
  week with no req-offs maxes out at exactly 13), so a req-off touching a dinner-eligible person
  on those days can newly tip the week into infeasibility. Confirmed via stress testing and kept
  intentionally, per explicit instruction, rather than lowering the floor or softening it.

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
