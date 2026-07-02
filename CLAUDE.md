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
- Lunch floor `Ltar=[9,9,9,9,10,10,10]`; dinner floor `Dhard=[10,10,10,11,13,13,11]` (Sunday matches Thursday's 11, not the generic weekday 10 — see "Soft targets" below); manager ≥45 and the weekly paid-hours bounds.
  - Lunch = shift spans noon (`a<=12<b`). Dinner = starts at/before 6pm **and** ends at/after 8pm (`a<=18 and b>=20`) — both conditions required, not just a late end; someone ending at 5/6/7pm no longer counts, even if they worked into the evening. (Previously dinner was just `b>17`; tightened per human request. `a<=18` is structurally always true given the anchor grid's 18:00 start ceiling, so `b>=20` is the only condition that actually discriminates today — kept explicit in case that ever changes.) **Known accepted risk:** Fri/Sat's floor of 13 now has ~zero slack — even a fully-staffed week with no req-offs maxes out at exactly 13, so a req-off touching a dinner-eligible person on those days can newly tip the week into infeasibility. Confirmed via stress testing; kept as-is per explicit instruction rather than lowering the floor or making it soft.
- Openers: exactly 3 people in by 9:00 (`stag9`, counting Bowen's 8a anchor) AND exactly 2 more starting at exactly 10:00 (`open10`) — both hard equalities, together always totaling 5/day. The old 9:15/9:30/9:45 stagger is gone (`gen()` now bans starts strictly between 9 and 10, same as the existing 10-11 ban), so an opener's only two valid start slots are "by 9" or "exactly 10".
- Closer floor: hard at `Ctar-1` (uniform 5 target every day → floor 4) — never allowed 2+ below target. Sitting exactly 1 below (4) carries a large penalty (`_close_graded`, `_CLOSE_PEN=900`) — human preference: 4 closers should be rare, not routine.
- At least 1 PB opener and 1 PB closer every day (`pb_op`/`pb_cl`) — was a soft floor (`_sf`) until stress testing showed the static `_pb_opener_exists`/`_pb_closer_exists` check (which only decides the manager backstop's backbone shift) doesn't guarantee the solver actually places anyone in that role; a genuinely-available PB member could get optimized into a non-opening/non-closing shift, leaving a day with zero PB coverage.
- Every person with at least one available day gets ≥1 shift for the week — hard, not the old big-penalty soft version. The only exemption is a person with zero available days at all (e.g. they req'd off their entire week).
- Trio-close rules:
  - **Mary Dean always closes when available.** Every non-backbone day she works is pruned to closing-only candidates, and a hard floor forces her to work all but 1 of her available days — so in practice she closes on `(available days − 1)`.
  - **James Baker never closes alongside Mary Dean** — hard, no penalty tier.
  - Absent Mary, at most 1 of Gobi/James/Trinity closes — this one is a **high-penalty soft ceiling** (`_TRIO_ESCAPE=1000`), not hard: see "Soft targets" below.

**Soft targets above those floors** (penalised, not hard):
- Sunday lunch aims for 11 (`Lsoft`, `_LUNCHPEN=800`).
- Dinner: tiny aspiration of hard-floor+1 on **every** day (`Dtar=Dhard+1`, `_DINPEN=20`) — deliberately far below every other coverage penalty, a nice-to-have nudge only. Sunday's floor itself (not the soft aspiration) was raised to match Thursday's (11, not the generic 10) — human preference: Sunday reliably hitting 11 outranks Thursday reaching a 12th body. Tried as a soft nudge first (even at 5000 — larger than every other soft weight, including `_TRIO_ESCAPE`) but HiGHS's time-limited heuristic search didn't reliably discover the improvement even though it's provably free (confirmed: forcing Sunday to 11 costs nothing and doesn't touch Thursday). Promoted to a hard floor instead, the same class of upgrade already applied to the PB opener/closer floors for the same reliability reason.
- Closers: `_CLOSE_PEN=900` for sitting exactly 1 below `Ctar` (i.e. at 4) — the only closer slack left; 2+ below is now the hard floor above. Weighted between `_LUNCHPEN`(800) and `_TRIO_ESCAPE`(1000) so a thin day gives up other tradeoffs (coverage ceilings, hour floors, even the lunch soft target) before settling for 4.
- Trio-cap escape valve: `_TRIO_ESCAPE=1000` lets a 2nd of Gobi/James/Trinity close (absent Mary) **only** as a last resort when the hard closer floor can't be met otherwise. The weight is higher than every other soft penalty so it's never worth paying for any other reason — verified it does NOT fire when the trio cap isn't the actual bottleneck, and DOES fire (via an isolated synthetic-model test) when it's the only way to reach the floor.
- Zac Duffy and Gracelyn Dailey: no hard hour cap for either — both target 30h with a penalty for missing it (Zac at `_HPEN_FT`/510 tier, Gracelyn at `_HPEN_STRONG`/200 tier via `strong_PT`), then fall under the generic 40h ceiling like everyone else.
- Reilly Weakley: hard-capped at 3 shifts/week (same pattern as Jacob Cothern's 2-shift cap) — his `FT_NONLEADER` floor is overridden to 24h (not the standard 33h) to match what 3 shifts can actually deliver, using the standard generic-loop floor+1 buffer like everyone else (no special case needed in `solver2.py`). Note the buffer is a no-op for him specifically: with floor == his real ceiling (no headroom above 24h to push into), `expr+slack>=24` and `expr+slack>=25` yield the identical optimal `expr` for every feasible value — the +1 trick only helps when true-max > floor. A 50-run stress batch showed the solver occasionally landing him at 23h even when 24h was reachable (ordinary MIP/gapRel imprecision on a floor quantized in whole 8h-shift increments, same class as Trinity Stringer's frequent 0.2h misses, just landing in a bigger unit). That's not a solver defect worth chasing — it's absorbed on the test side via `SHIFT_CAP_GRID_TOLERANCE_H` in `test_protocol.py` (anyone with a below-default `SHIFT_CAP` gets a wider grid-tolerance allowance than the generic `GRID_TOLERANCE_H`, since their achievable hours move in whole-shift jumps, not smooth fractions).

Priority order: `hard floors >> TRIO_ESCAPE(1000) > CLOSE_PEN(900) > LUNCH(800) > HPEN_LEADER(520) > HPEN_FT(510) > ceilings(_CPEN 500) > HPEN_STRONG(200) > HPEN_REG(150) > HPEN_WEAK(100) > DIN(20, every day)`. `HPEN_LEADER`/`HPEN_FT` (leader/FT-nonleader hours floor) sit just above the generic coverage ceilings — deliberately, after stress testing showed an achievable leader/FT hours floor was occasionally sacrificed to avoid a trivial coverage-ceiling nick when it sat below. `TRIO_ESCAPE` sits above everything else soft so it's genuinely a last resort, only ever paid when the hard closer floor has no other way to be met.

### Hours-floor priority cascade (`_hrs_slk`, 5 tiers)
When multiple people are competing for the same scarce leftover hours (a thin week, req-offs
depleting the flexible pool), the objective fills the "harder-working" tiers first, mirroring
the existing role hierarchy rather than a new ranking: **`leader` (PB, 520) > `ft` (FT
non-leaders + Zac Duffy, 510) > `strong` (strong_PT, 200) > `reg` (regular_PT, 150) > `weak`
(weak5, 100)**. `_sh(expr, floor, tag, tier=..., afl=None)` takes the tier explicitly;
`_sh_floor(n, floor, tag, max_per_day, tier=...)` is the per-person convenience wrapper used by
most call sites. LEADER/FT stay above `_CPEN`(500) — same reasoning as the old single "HI" tier;
STRONG/REG/WEAK stay well below `_CLOSE_PEN`(900) — same relative position the old single "LO" tier
had, just subdivided three ways instead of lumped together.

### Hours floor: reachable-hours fallback (don't drop the incentive when the full floor is out of reach)
`_sh_floor()`'s gate (`avail_days(n) >= ceil(floor/max_per_day)`) decides whether the *full*
floor is reachable this week. When it isn't (e.g. someone req'd off most of the week), the old
behavior for most groups (`FT_NONLEADER`/`regular_PT`/`strong_PT`/`weak5` loops, and the
individual Bowen/Trinity/Gobi/Mary calls) was to skip the hours-floor incentive **entirely** —
found via a live-schedule bug report: Ava Shade had exactly 1 available day this week (req'd off
the other 5, unavailable the 6th), her 33h floor needs 4 days to even engage the gate, so she got
*zero* hour-floor pressure and was left at the 4h minimum shift length, even though her one
available day could easily fit a full 10h shift (she's `TEN_HR`-eligible) with no cost to anyone
else. Jay/Myles/James/Adam already had individual hand-written fallbacks for this (push toward
the floor anyway even below the day-count gate) — `_sh_floor()` now generalizes that fallback to
everyone via `_reachable_hours(n, cap)`: sum of the longest candidate shift per available day
(from the already-`gen()`-filtered `shifts[(n,d)]`, so it respects availability/backbone/
`MUST_CLOSE_AT`/etc.), capped at the person's normal floor. This ignores cross-day interactions
(12h rest rule, the ≤5-shift cap) and can slightly overstate the true max — harmless, since it's
only an objective incentive; `_sh`'s slack absorbs whatever turns out unreachable, same as the
+1 buffer does for a normal floor. The audit's reported target (`afl`) is this scaled reachable
value instead of the person's full nominal floor, so "HoursUnder: Ava Shade Xh (target ≥Yh)"
tells you what was actually achievable *this week*, not a permanently-unreachable nominal number.

### Pre-filtered variable lists (`_SDF`)
Built once before the constraint loop at `# === MIP VARIABLES ===`. Maps `(day, tag) → list[LpVariable]`. Grep that section for full tag list.

### Paid hours vs raw hours
`NO_BREAK = {Jay, Myles}` — only managers get paid = raw hours.
All others: paid = raw − 0.5 if raw ≥ 5h, else raw.
`paid_val(n, a, b)` computes this. Hours floor constraints use RAW hours (b−a).

**11pm → 10:45 paid adjustment.** Closers scheduled to 11pm (end 23.0) almost always finish and clock out ~10:45, so `paid_val` counts an 11pm end as 22.75 (a −0.25h deduction, same principle as the break). Because it lives in `paid_val`, it flows through **everywhere paid hours matter** — including the weekly `[allowed+25, allowed+30]` and per-day budget bands — giving the solver ~0.25h/closer (~4h/week) more clock time to schedule. Hours-FLOOR constraints use raw `b−a` (not `paid_val`), so target hours are untouched. The schedule grid still SHOWS 11pm (cells render raw shift times). The `Status: … var` solver line and the `TOTAL var` reporting now agree (both on adjusted hours).

### Hours floor buffer
All full-floor (gate-passed) penalty targets are set +1h above the real floor (e.g. floor=39 → penalty target=40). The `afl=` param stores the real floor for audit display. Absorbs ~0.75h gapRel undershoot so early-stop never reports a false miss. (The reachable-hours fallback path — see above — does NOT use this +1 buffer: when `floor == the real achievable ceiling` for the week, floor and floor+1 targets are mathematically identical optimization problems, so the buffer would be a pure no-op, same lesson learned from Reilly Weakley's 3-shift cap.)

### Objective (minimise)
`8*weak_use + 0.3*short_pref + 30*mgr_offday + 20*jay_closes + 20*myles_opens + 500*cov_slk + 900*close_pen + 1000*trio_escape + 800*lunch_slk + 20*din_slk + 520*hrs_leader_slk + 510*hrs_ft_slk + 200*hrs_strong_slk + 150*hrs_reg_slk + 100*hrs_weak_slk` (+ small per-person above-floor nudge). The ≥1-shift rule, the closer floor at `Ctar-1`, the exact opener timing, and James-never-with-Mary are all hard constraints, not part of this objective — only the at-most-1-of-Gobi/James/Trinity cap (absent Mary) is soft, via `trio_escape`.
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
- `FT_nonleader` — Adam Van Bogaert, Mason Doyle, Michael Calderon, Molly Summers, Noah Hiner, Ava Shade, Izzy Simpson, Remi Sullinger, Reilly Weakley, Zac Duffy (33–40h target; Adam/Reilly/Zac each carry their own `_FLOOR` override — 40h/24h/30h respectively — same group, different per-person target)
- `strong_PT` — Gracelyn Dailey, Cai Cotton, Sandy Wright, Kara Thompson, Nathan Paaswee, Peyton Shaw, Reese Bezehertny, Diana Castaneda, Kayden Anderson, Ryder Buccola (20h target)
- `regular_PT` — Amiyah Bartley, Harper Flynn, Jonathan Beacham, Hayden Roush, Logan Frias, Richard Raglin (12h target)
- `_trio` — Gobi, James, Trinity, Mary Dean: Mary always closes when available (hard); James never closes with Mary (hard); absent Mary, at most 1 of Gobi/James/Trinity closes (soft escape valve — see "Constraint model" above)

## Session preferences

### New rules/instructions: propagate to every relevant file, not just one
When you add, change, or remove a business rule, constraint, or per-person special case, update
**every file that rule touches** in the same pass — don't stop at `solver2.py`:
- `solver2.py` — the actual constraint/logic.
- `backbone.py` — if it's a shared constant, group, or per-person override. Prefer putting new
  per-person special cases here (like `WEEKEND_MAKEUP`, `SHIFT_CAP`, `WEAK5_MAX_DAYS`) rather than
  hardcoding them in `solver2.py`, specifically so `test_protocol.py` can import the same source
  instead of drifting.
- `test_protocol.py` — if the rule affects reachable hours/shifts, update the hour-reachability
  DP (`_max_achievable_raw`) and/or the manager-backbone approximation (`_BACKBONE_SHIFTS`) so the
  stress test's hard/soft failure classification doesn't silently rely on a stale assumption.
- `scheduling_rules.md` — the narrative business-rule description a human would read.
- `CLAUDE.md` (this file) — if it's an architectural/objective/constraint-model detail worth
  documenting for future sessions.
- `CHANGELOG.md` — a one-line entry if it's a notable, non-routine-data change.
Before considering a rule change done, do a quick pass across this list — this repo has already
drifted more than once when a rule landed in only one file (e.g. `WEEKEND_MAKEUP` shipped without
a `test_protocol.py` update or a `CHANGELOG.md` entry; Reilly's "max 3 shifts" rule existed only
in `scheduling_rules.md` with no matching constraint in `solver2.py`). A full audit later caught
both, but the point is to not need one.

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

### Stress-test seeds: don't hand-pick/reuse a seed as a stand-in for real verification
`TEST_SEED` pins the RNG so a run is exactly reproducible — that's it. Do NOT treat "run it again
with some seed" as a second, independent data point; a single seed's outcome doesn't generalize,
and re-running the *same* seed produces a byte-identical result, so it proves nothing new no
matter how many times it's repeated. There is exactly one legitimate reason to fix a seed:
isolating the effect of one specific code change via a controlled before/after comparison (same
random conditions, only the code differs — as done for the `WEEKEND_MAKEUP`/Reilly-cap
regression tests). Outside that specific use, always let `TEST_SEED` auto-randomize (the
default) — never hand-pick a seed, and never call a repeat run at a fixed or newly-hand-picked
seed "extra confidence." If genuinely more confidence is wanted, that means more `TEST_RUNS` in
one unseeded batch, not another single seeded run.

## Weekly workflow — the human provides inputs, Claude does the rest
**The human only supplies the three input files for the new week** (availability, request-offs,
forecast). Everything below is **Claude's job** — do not ask the human to edit the backbone or
run the solver; that's the whole point of this split.

Given the new inputs, Claude:
1. Overwrites `avail.json` / `reqoff.json` / `forecast.json` with the new week's contents (set
   `week_start` in `forecast.json`). Filenames are stable — no rename, no code edit to point at them.
   **`avail.json` must always start from each person's standard/default availability** (the master
   roster PDF + the documented FT patterns in `scheduling_rules.md` §10, e.g. Jay's Mon/Thu/Fri/Sat/
   Sun working days with only Tue/Wed off) — never carry a prior week's one-off request-off forward
   as a baked-in "X". Request-offs are week-scoped and belong ONLY in `reqoff.json`; if a person's
   day-off request from a previous week ends up sitting in `avail.json` as unavailability, that's a
   bug, not a standing pattern — restore it. This applies to literally everyone, managers included
   (caught once: Jay Martin's Monday had been stuck at "X" for several weeks from a stale edit,
   silently cutting his hours from 45 to as low as 26 before it was traced and fixed). The only
   legitimate reasons `avail.json` deviates from someone's standard pattern are a genuine standing
   availability change (e.g. Gracelyn's monthly calendar, always re-verified fresh) or a real
   ongoing note for *this specific* week that isn't a simple day-off (e.g. Gobi needing to leave by
   2pm on a specific Tuesday) — never a mechanically-carried-over previous week's request-off.
2. **Derives and updates the backbone in `backbone.py`** from those inputs + `scheduling_rules.md`:
   `STATIC_BACKBONE` for non-managers (who's fixed to which shift this week — e.g. anyone on vacation
   gets no backbone), and `JAY_STD`/`JAY_OPEN`/`MYLES_STD`/`MGR_OFFDAY_SHIFT` for the managers' standard
   and backstop shifts. `backbone.py` is the single source of truth — `solver2.py` and `test_protocol.py`
   both import it, so the stress test can't drift from the live backbone.
3. Runs `python solver2.py`.
4. Reads the printed audit, fixes flagged issues (adjust the backbone / inputs), and re-runs until clean.
5. Reports the final schedule + audit back to the human; commits and (per session prefs) opens/merges the PR.
