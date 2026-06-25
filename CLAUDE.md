# Schedule Solver — Architecture Reference

## What this is
MIP (Mixed Integer Programming) weekly shift scheduler for Paddock restaurant. Uses PuLP + HiGHS.

Primary file: `solver2.py`. Read `scheduling_rules.md` for the full business rules.

## Input files (change each week)
- `avail_6_29.json` — availability per person per day (array of 7 days)
- `reqoff_6_29.json` — request-offs by day name
- `forecast_6_29.json` — `{"allowed_hours": [Mon..Sun]}`

## Key design decisions

### Soft-constraint model
All coverage constraints use penalised slack variables (`_CPEN=500`) instead of hard equalities — widens the feasible region so HiGHS finds the first integer-feasible point faster. Slacks are always 0 in any optimal solution. Helpers: `_sc(e, cap, t)` ceiling, `_sf(e, fl, t)` floor, `_sh(expr, floor, tag, hi, afl)` hours floor with penalty tier.

### Pre-filtered variable lists (`_SDF`)
Built once before the constraint loop at `# === MIP VARIABLES ===`. Maps `(day, tag) → list[LpVariable]`. Grep that section for full tag list.

### Paid hours vs raw hours
`NO_BREAK = {Jay, Myles}` — only managers get paid = raw hours.
All others: paid = raw − 0.5 if raw ≥ 5h, else raw.
`paid_val(n, a, b)` computes this. Hours floor constraints use RAW hours (b−a).

### Hours floor buffer
All `hi=True` penalty targets are set +1h above the real floor (e.g. floor=39 → penalty target=40). The `afl=` param stores the real floor for audit display. Absorbs ~0.75h gapRel undershoot so early-stop never reports a false miss.

### Objective (minimise)
`5000*zero_pen + 8*weak_use + 0.3*short_pref + 30*mgr_offday + 500*cov_slk + 490*hrs_hi_slk + 150*hrs_lo_slk`
- Weekly paid hours hard-bounded to `[sum(allowed)+25, sum(allowed)+30]`
- `zero_pen` — big penalty if any available person gets 0 shifts
- `weak_use` — discourage weak5 extra shifts
- `short_pref` — light penalty for 5–5.5h shifts (prefer 4–4.5h)

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

## Common weekly tasks
1. Update availability/reqoff/forecast JSON files (rename `avail_6_29.json` etc. to new date)
2. Update backbone `fx()` calls in `# ===== BACKBONE =====` section of solver2.py
3. Run: `python solver2.py`
4. Read the printed audit — fix flagged issues and re-run
