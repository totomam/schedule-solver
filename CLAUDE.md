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
All coverage CEILING constraints use penalised slack variables (`_CPEN=500`), not hard equalities.
This widens the LP feasible region → HiGHS finds a first feasible integer point ~35% faster.
`_CPEN >> max possible objective gain (~80)` so slacks are always 0 in the optimal solution —
the final schedule is identical to the hard-equality version.

Helpers at lines ~175:
- `_sc(e, cap, t)` — soft ceiling: `e <= cap + slack`
- `_sf(e, fl, t)` — soft floor: `e + slack >= fl`

### Pre-filtered variable lists (`_SDF`)
Built once before the constraint loop. Maps `(day, tag) → list[LpVariable]`.
Tags: `h14 h15 h155 h16 h165 opener lunch dinner cl225 cl21 cl215 pb_op pb_cl w3_ln w3_dn
       la1725 la175 la1775 la18 dep20 dep205 dep14 trio_cl stag9 prep9`

### Shift candidates
`gen(n, d)` produces all (start, end) pairs on 15-min grid within availability, respecting:
- 4h minimum shift length, 8h max PT / 10h max for `TEN_HR` set
- No start before 9am except PB (leaders/managers)
- No ends 5pm < b < 8pm, no 8:15/8:45 ends
- No end before 2pm (3pm Sunday)
- Adam Van Bogaert always ends at 11pm
- Molly Summers never past 5pm

`dedup()` collapses candidates with identical coverage signatures (`_sig()`) to reduce variables.

### 12h close-then-open rule
Aggregated per `(person, day, close-end-time)`: one constraint per group rather than per pair.
Lines ~267–282.

### Paid hours vs raw hours
`NO_BREAK = {Jay, Myles}` — only managers get paid hours = raw hours.
All others: paid = raw − 0.5 if raw ≥ 5h, else raw.
`paid_val(n, a, b)` computes this. Hours constraints use RAW hours (b−a).

### Objective (minimise)
`50*zero_pen_sum + 8*weak_use + 0.3*short_pref + 500*cov_slk_sum`
- Total paid hours constrained to `[sum(allowed)+25, sum(allowed)+30]` as hard bounds — no penalty term, any value in the window is equally acceptable.
- `zero_pen` = big penalty if any available person gets 0 shifts
- `weak_use` = discourage weak5 group (Layton, Emily, Brian, Bryan, Jason) from extra shifts
- `short_pref` = light penalty for 5–5.5h shifts (prefer 4–4.5h)

### Solver parameters
`HiGHS(msg=False, timeLimit=240, gapRel=0.25)`
`SCHED_THREADS` env var enables parallel B&B.

`gapRel=0.25` not `0.01`: profiling showed HiGHS finds its best feasible solution at ~83s via
Sub-MIP heuristic and never improves it during the remaining B&B (only the dual bound moves).
The MIP gap is structurally ~18-22% (driven by coverage slack integrality) so gapRel=0.01 always
hit the 240s time limit without closing. gapRel=0.25 terminates at ~90s — same schedule, 62% faster.

## Output
Writes `schedule.json` (all people) and `schedule_active.json` (worked days only).
Prints a summary table and inline rules audit — no separate audit script needed.

## People groups
- `PB` — shift leaders + managers (7 people)
- `NO_BREAK` — Jay + Myles (no break deduction)
- `TEN_HR` — allowed 10h shifts
- `weak3` — Brian Carver, Bryan Bishop, Jason Britt (1-per-meal-period rule)
- `weak5` — weak3 + Layton Angermeier + Emily Owens (prefer-1-day rule)
- `prep` — prep crew (must have ≥1 starting ≤9am each day)
- `FT_nonleader` — full-time non-leaders (35–40h target)
- `_trio` — Gobi, James, Trinity (at most 1 closes per day)

## Common weekly tasks
1. Update availability/reqoff/forecast JSON files
2. Update backbone `fx()` calls in solver2.py for any week-specific fixed shifts
3. Run: `python solver2.py` (or `time python solver2.py`)
4. Read the printed audit — fix any flagged issues and re-run
