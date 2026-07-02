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
- Lunch floor `Ltar=[9,9,9,9,10,10,10]`; dinner floor `Dhard=[10,10,10,11,13,13,10]`; manager ≥45 and the weekly paid-hours bounds.
- Openers: exactly 3 people in by 9:00 (`stag9`, counting Bowen's 8a anchor) AND exactly 2 more starting at exactly 10:00 (`open10`) — both hard equalities, together always totaling 5/day. The old 9:15/9:30/9:45 stagger is gone (`gen()` now bans starts strictly between 9 and 10, same as the existing 10-11 ban), so an opener's only two valid start slots are "by 9" or "exactly 10".
- Closer floor: hard at `Ctar-1` (5 Mon-Thu / 6 Fri-Sun → floor 4/5) — never allowed 2+ below target. Only sitting exactly 1 below is still just a small penalty (`_close_graded`).
- At least 1 PB opener and 1 PB closer every day (`pb_op`/`pb_cl`) — was a soft floor (`_sf`) until stress testing showed the static `_pb_opener_exists`/`_pb_closer_exists` check (which only decides the manager backstop's backbone shift) doesn't guarantee the solver actually places anyone in that role; a genuinely-available PB member could get optimized into a non-opening/non-closing shift, leaving a day with zero PB coverage.
- Every person with at least one available day gets ≥1 shift for the week — hard, not the old big-penalty soft version. The only exemption is a person with zero available days at all (e.g. they req'd off their entire week).
- Trio-close rules:
  - **Mary Dean always closes when available.** Every non-backbone day she works is pruned to closing-only candidates, and a hard floor forces her to work all but 1 of her available days — so in practice she closes on `(available days − 1)`.
  - **James Baker never closes alongside Mary Dean** — hard, no penalty tier.
  - Absent Mary, at most 1 of Gobi/James/Trinity closes — this one is a **high-penalty soft ceiling** (`_TRIO_ESCAPE=1000`), not hard: see "Soft targets" below.

**Soft targets above those floors** (penalised, not hard):
- Sunday lunch aims for 11 (`Lsoft`, `_LUNCHPEN=800`).
- Dinner: tiny uniform aspiration of hard-floor+1 on **every** day (`Dtar=Dhard+1`, `_DINPEN=20`) — deliberately far below every other coverage penalty, a nice-to-have nudge only. (No longer Sunday-specific/heavy.)
- Closers: `_CLOSE_SMALL=300` for sitting exactly 1 below `Ctar` — the only closer slack left; 2+ below is now the hard floor above.
- Trio-cap escape valve: `_TRIO_ESCAPE=1000` lets a 2nd of Gobi/James/Trinity close (absent Mary) **only** as a last resort when the hard closer floor can't be met otherwise. The weight is higher than every other soft penalty so it's never worth paying for any other reason — verified it does NOT fire when the trio cap isn't the actual bottleneck, and DOES fire (via an isolated synthetic-model test) when it's the only way to reach the floor.
- Zac Duffy and Gracelyn Dailey: no hard hour cap for either — both target 30h with a penalty for missing it (Zac at `_HPEN_HI`/510 tier, Gracelyn at `_HPEN_LO`/150 tier via `strong_PT`), then fall under the generic 40h ceiling like everyone else.

Priority order: `hard floors >> TRIO_ESCAPE(1000) > LUNCH(800) > HPEN_HI(510) > ceilings(_CPEN 500) > CLOSE_SMALL(300) > HPEN_LO(150) > DIN(20, every day)`. `HPEN_HI` (shift-leader/FT-nonleader hours floor) sits just above the generic coverage ceilings — deliberately, after stress testing showed an achievable leader/FT hours floor was occasionally sacrificed to avoid a trivial coverage-ceiling nick when it sat below. `TRIO_ESCAPE` sits above everything else soft so it's genuinely a last resort, only ever paid when the hard closer floor has no other way to be met.

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
`8*weak_use + 0.3*short_pref + 30*mgr_offday + 20*jay_closes + 20*myles_opens + 500*cov_slk + 300*close_small + 1000*trio_escape + 800*lunch_slk + 20*din_slk + 510*hrs_hi_slk + 150*hrs_lo_slk` (+ small per-person above-floor nudge). The ≥1-shift rule, the closer floor at `Ctar-1`, the exact opener timing, and James-never-with-Mary are all hard constraints, not part of this objective — only the at-most-1-of-Gobi/James/Trinity cap (absent Mary) is soft, via `trio_escape`.
- Weekly paid hours hard-bounded to `[sum(allowed)+25, sum(allowed)+30]`
- `weak_use` — discourage weak5 extra shifts
- `short_pref` — light penalty for 5–5.5h shifts (prefer 4–4.5h)
- `jay_closes`/`myles_opens` — small penalty (20, below `mgr_offday`'s 30) so the backstop manager role stays out of the other's preferred edge (Jay opens, Myles closes) unless coverage genuinely needs it
- See "Constraint model" above for the coverage hard-floor / soft-target hierarchy.

### Solver parameters
`HiGHS(timeLimit=240, gapRel=0.25)` — env vars `SCHED_TIMELIMIT`, `SCHED_GAPREL`, `SCHED_THREADS`, `SCHED_HIGHS_SEED`.

`gapRel=0.25`: HiGHS finds its best solution at ~83s via Sub-MIP heuristic and never improves it; only the dual bound moves. MIP gap is structurally ~18-22% so gapRel=0.01 always hit the 240s limit. gapRel=0.25 exits at ~90s — same schedule, 62% faster.

### Infeasibility diagnostic
When the main solve is `Infeasible`, every tagged hard coverage floor (`_hard_diag_log` — lunch,
dinner, opener count, PB opener/closer, closer floor, the exact-3@9/exact-2@10 equalities) is
replayed as a soft constraint on the *same* `prob` object, the objective is swapped to "minimize
total shortfall", and it's re-solved once (capped at 60s). This isolates exactly which floor(s)
and day(s) are the real blocker and prints it in the `FATAL` message — no schedule is ever written
from this pass, it's purely diagnostic. Scope is coverage floors only: if the true blocker
involves something outside that set (the per-day/weekly paid-hours bands, per-person hour
equalities, shift-count caps, the 12h rest rule), the diagnostic re-solve stays Infeasible too and
says so explicitly ("Diagnostic inconclusive... outside coverage floors") rather than guessing.

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
- `_trio` — Gobi, James, Trinity, Mary Dean: Mary always closes when available (hard); James never closes with Mary (hard); absent Mary, at most 1 of Gobi/James/Trinity closes (soft escape valve — see "Constraint model" above)

## Session preferences

### Git/GitHub: the human does not use GitHub — never ask, just handle it
The human knows nothing about Git or GitHub and does not want to. **Never ask them anything
about branches, commits, pushes, pull requests, or merging** — not "should I open a PR?", not
"want me to merge?", not "keep going on the branch or merge?". Use your best judgement and do
the whole thing yourself. The default end-to-end flow, with no confirmation at any step:
1. Commit the change on the working branch.
2. Push.
3. Open a PR (only when there's a coherent unit of work to land — you don't need a PR per commit).
4. **Merge it to main yourself** as soon as it's green/ready.
Only surface Git to the human if something is genuinely stuck (e.g. a conflict you can't safely
resolve) and you actually need a decision only they can make — and even then, frame it in plain
English, not Git jargon. Report *what shipped*, not *whether to ship it*.

### Deliverables
- When asked for "the schedule", deliver the **`schedule.xlsx` file** (via the file-send tool),
  not just an inline table. Lead with the file.

### Stress-test run count
- Default `TEST_RUNS=10` for any randomized `test_protocol.py` stress run. Only use a larger count
  (e.g. 30/50) when the human explicitly asks for one, and treat that as a one-time request — the
  default reverts to 10 afterward, not to whatever was last requested.

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
