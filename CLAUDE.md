# Schedule Solver — Architecture Reference

## What this is
MIP (Mixed Integer Programming) weekly shift scheduler for Paddock restaurant. Uses PuLP + HiGHS.

Primary file: `solver2.py`. Read `scheduling_rules.md` for the full business rules.

## Input files (stable names — overwrite contents each week, no rename/code edit)
- `avail.json` — availability per person per day (array of 7 days)
- `reqoff.json` — request-offs by day name
- `forecast.json` — `{"week_start": "YYYY-MM-DD", "allowed_hours": [Mon..Sun], ...}`. The week's
  date lives here in `week_start` (feeds the Excel headers), so the filenames never carry a date.
- `stress_avail.json` / `stress_reqoff.json` / `stress_forecast.json` — frozen baseline for
  `test_protocol.py` (NOT the live week; deliberately fixed so the stress suite is reproducible).

## Key design decisions

### Constraint model — hard floors + penalised soft constraints
Most coverage uses penalised slack variables (`_CPEN=500`) so the feasible region stays wide and HiGHS converges fast. Helpers: `_sc` ceiling, `_sf` floor, `_sh` hours floor (tiered), `_close_graded` graduated closers, `_sfl`/`_sfd` lunch/dinner soft targets.

**Hard floors** (`_hardfloor` → infeasible, a real fail, if unmet — the solver never returns a schedule that misses them):
- Lunch floor `Ltar=[9,9,9,9,10,10,10]`; dinner floor `Dhard=[10,10,10,11,14,13,10]`; openers `Otar=5`/day. Plus manager ≥45 and the weekly paid-hours bounds.

**Soft targets above those floors** (penalised, not hard):
- Sunday lunch aims for 11 (`Lsoft`, `_LUNCHPEN=800`); Sunday dinner aims for 11 (`Dtar`, `_DINPEN=300`).
- Closers: graduated — `_CLOSE_SMALL=300` for 1 below `Ctar` (5 wk/6 wknd), `_CLOSE_MASSIVE=4000` for 2+ below (basically never).

Priority order: `hard floors >> CLOSE_MASSIVE(4000) > LUNCH(800) > DIN(790) > ceilings(_CPEN 500) > CLOSE_SMALL(300)`. Dinner→11 ranks just below the lunch push, above the afternoon ceilings and the 6th closer, but below the massive closer floor — so a thin Sunday protects dinner 11 ahead of those, yet never drops closers to 4 to get it.

### Pre-filtered variable lists (`_SDF`)
Built once before the constraint loop at `# === MIP VARIABLES ===`. Maps `(day, tag) → list[LpVariable]`. Grep that section for full tag list.

### Paid hours vs raw hours
`NO_BREAK = {Jay, Myles}` — only managers get paid = raw hours.
All others: paid = raw − 0.5 if raw ≥ 5h, else raw.
`paid_val(n, a, b)` computes this. Hours floor constraints use RAW hours (b−a).

**11pm → 10:45 paid adjustment.** Closers scheduled to 11pm (end 23.0) almost always finish and clock out ~10:45, so `paid_val` counts an 11pm end as 22.75 (a −0.25h deduction, same principle as the break). Because it lives in `paid_val`, it flows through **everywhere paid hours matter** — including the weekly `[allowed+25, allowed+30]` and per-day budget bands — giving the solver ~0.25h/closer (~4h/week) more clock time to schedule. Hours-FLOOR constraints use raw `b−a` (not `paid_val`), so target hours are untouched. The schedule grid still SHOWS 11pm (cells render raw shift times). The `Status: … var` solver line and the `TOTAL var` reporting now agree (both on adjusted hours).

### Hours floor buffer
All `hi=True` penalty targets are set +1h above the real floor (e.g. floor=39 → penalty target=40). The `afl=` param stores the real floor for audit display. Absorbs ~0.75h gapRel undershoot so early-stop never reports a false miss.

### Objective (minimise)
`5000*zero_pen + 8*weak_use + 0.3*short_pref + 30*mgr_offday + 500*cov_slk + 4000*close_massive + 800*lunch_slk + 790*din_slk + 300*close_small + 490*hrs_hi_slk + 150*hrs_lo_slk` (+ small per-person above-floor nudge)
- Weekly paid hours hard-bounded to `[sum(allowed)+25, sum(allowed)+30]`
- `zero_pen` — big penalty if any available person gets 0 shifts
- `weak_use` — discourage weak5 extra shifts
- `short_pref` — light penalty for 5–5.5h shifts (prefer 4–4.5h)
- See "Constraint model" above for the coverage hard-floor / soft-target hierarchy.

### Solver parameters
`HiGHS(timeLimit=240, gapRel=0.25)` — env vars `SCHED_TIMELIMIT`, `SCHED_GAPREL`, `SCHED_THREADS`, `SCHED_HIGHS_SEED`.

`gapRel=0.25`: HiGHS finds its best solution at ~83s via Sub-MIP heuristic and never improves it; only the dual bound moves. MIP gap is structurally ~18-22% so gapRel=0.01 always hit the 240s limit. gapRel=0.25 exits at ~90s — same schedule, 62% faster.

## People groups
- `PB` — shift leaders + managers: Jay Martin, Myles Palmer, Bowen Benedict, James Baker, Trinity Stringer, Gobi Weathers, Mary Dean
- `NO_BREAK` — Jay + Myles (no break deduction)
- `TEN_HR` — PB + Adam Van Bogaert, Mason Doyle, Ava Shade, Remi Sullinger, Izzy Simpson, Zac Duffy, Kara Thompson
- `weak3` — Brian Carver, Bryan Bishop, Jason Britt (1-per-meal-period rule)
- `weak5` — weak3 + Emily Owens, Shayden Howard, Oliver Croasdaile, John Dugan (prefer-1-day rule)
- `prep` — Michael Calderon, Tiffany Huffman, Noah Hiner, Gracelyn Dailey, Molly Summers, Reilly Weakley (≥1 starting ≤9am each day)
- `FT_nonleader` — Adam Van Bogaert, Mason Doyle, Michael Calderon, Molly Summers, Noah Hiner, Ava Shade, Izzy Simpson, Remi Sullinger, Reilly Weakley (33–40h target)
- `strong_PT` — Gracelyn Dailey, Cai Cotton, Sandy Wright, Kara Thompson, Nathan Paaswee, Peyton Shaw, Reese Bezehertny (20h target)
- `regular_PT` — Amiyah Bartley, Harper Flynn, Jonathan Beacham, Hayden Roush, Logan Frias, Kayden Anderson, Richard Raglin, Ryder (12h target)
- `_trio` — Gobi, James, Trinity (at most 1 closes per day)

## Session preferences
- When a PR is complete and ready, merge it to main without asking first.

## Weekly workflow — the human provides inputs, Claude does the rest
**The human only supplies the three input files for the new week** (availability, request-offs,
forecast). Everything below is **Claude's job** — do not ask the human to edit the backbone or
run the solver; that's the whole point of this split.

Given the new inputs, Claude:
1. Overwrites `avail.json` / `reqoff.json` / `forecast.json` with the new week's contents (set
   `week_start` in `forecast.json`). Filenames are stable — no rename, no code edit to point at them.
2. **Derives and updates the backbone in `backbone.py`** from those inputs + `scheduling_rules.md`:
   `STATIC_BACKBONE` for non-managers (who's fixed to which shift this week — e.g. anyone on vacation
   gets no backbone), and `JAY_STD`/`JAY_OPEN`/`MYLES_STD`/`MGR_OFFDAY_SHIFT` for the managers' standard
   and backstop shifts. `backbone.py` is the single source of truth — `solver2.py` and `test_protocol.py`
   both import it, so the stress test can't drift from the live backbone.
3. Runs `python solver2.py`.
4. Reads the printed audit, fixes flagged issues (adjust the backbone / inputs), and re-runs until clean.
5. Reports the final schedule + audit back to the human; commits and (per session prefs) opens/merges the PR.
