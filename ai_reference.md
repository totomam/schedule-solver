# Paddock Solver — AI Session Reference

**Step 1 — fetch the solver before editing anything:**
`https://raw.githubusercontent.com/totomam/schedule-solver/main/solver2.py`

**Full human rules (narrative, checklist, examples):**
`https://raw.githubusercontent.com/totomam/schedule-solver/main/scheduling_rules.md`

---

## People Groups
- `PB` (leaders + managers): Jay, Myles, Bowen, James, Trinity, Gobi, Mary
- `NO_BREAK` (paid hours = raw hours, no break deduction): Jay, Myles only
- `TEN_HR` (10h max shifts): all PB + Adam, Mason, Michael, Molly, Noah, Ava, Remi, Izzy, Zac, Kara
- `weak3` (1-per-meal-period rule): Brian Carver, Bryan Bishop, Jason Britt
- `weak5` (prefer-1-day): weak3 + Layton Angermeier, Emily Owens
- `prep` (≥1 must start ≤9am every day): Michael, Tiffany, Noah, Gracelyn, Molly, Reilly
- `FT_nonleader` (35–40h target): Adam, Mason, Michael, Molly, Noah, Ava, Izzy, Remi
- `_trio` (at most 1 closes per day): Gobi, James, Trinity

---

## Hour Targets
| Person / Group | Range |
|---|---|
| Jay | 47h standard (soft — can work less if req-off) |
| Myles | 45h standard (soft — can work less if req-off) |
| Bowen, James, Trinity, Mary | 39–40h raw |
| Gobi | 37–40h (fixed schedule caps at ~37h) |
| FT_nonleader (≥5 avail days) | 35–40h |
| Adam (Fri req-off this week) | ≥35h |
| Zac Duffy | 30–35h |
| Gracelyn Dailey | 20–30h |
| Medium PT | ≥15h each |
| Everyone else | ≤40h |

---

## Coverage Targets (indices 0–6 = Mon–Sun)
```
Otar  (openers ≤10am, excl. Jay) = [6,6,6,6,6,6,6]
Ltar  (at noon)                  = [9,9,9,9,10,10,11]
Dtar  (past 5pm)                 = [10,10,10,11,14,13,12]
Ctar  (closers ≥10:30pm)         = [5,5,5,5,6,6,6]
twoTar   (at 2pm headcount)      = [8,8,8,8,8,9,11]
threeTar (at 3pm headcount)      = [6,6,6,6,7,8,8]
fourTar  (at 4pm headcount)      = [5,5,5,5,6,7,6]
```
- Past 9pm: ≥7 Mon–Thu/Sun; exactly 8 Fri/Sat
- Past 9:30pm: ≥6 Mon–Thu; ≥7 Fri–Sun

---

## Closer End-Time Staggering (soft equality, every day)
- 2 × 11:00pm (23.0) · 2 × 10:30pm (22.5) · 1 × 10:15pm (22.25) · 1 × 10:45pm (22.75)
- On 5-closer days (Mon–Thu, Sun) the solver drops one slot naturally

---

## Per-Person Rules (enforced in gen())
- **Adam Van Bogaert**: every shift ends at exactly 11pm (23.0)
- **Shift leaders** (Bowen, James, Trinity, Gobi, Mary): if shift ends ≥10pm, must end at exactly 11pm
- **Molly Summers**: never past 5pm (hi capped at 17)
- **All PB except Jay/Bowen**: 9am start floor — exceptions: Gobi & Trinity on Sat (d=5), James on Sun (d=6) may start at 8am

---

## Manager Standard Schedules (solver-placed each week within avail windows)
| Manager | Standard days | Standard shift | Hours | Normal days off |
|---|---|---|---|---|
| Jay | Mon/Thu/Fri/Sat/Sun | Mon 6–3, Thu/Fri/Sat 10–8, Sun 11–5 | 47h | Tue/Wed |
| Myles | Mon/Tue/Wed/Sat/Sun | Mon/Sun 12–9, Tue/Wed 11–8, Sat 12–9 | 45h | Thu/Fri |

Both are solver-placed (no `fx()` calls). Can close at 11pm when no shift leader is available; Jay covers if Myles is also unavailable. Days off are flexible — if one requests off, the other adjusts.

**Deviation Rule 1 — day swap on req-off:**
- Jay requests off Thu or Fri → Myles covers that day; Myles takes a different day off; Jay works Myles's normal off day (Thu or Fri).
- Myles requests off Tue or Wed → Jay covers that day; Jay takes a different day off; Myles works Jay's normal off day (Tue or Wed).
- Apply by updating avail JSON: open the covering manager on the new day, mark the requesting manager's original day X.

**Deviation Rule 2 — coverage backstop:**
- If leaders request off such that a day has no leader opener (≤10am) or closer (≥10pm), a manager fills in.
- Myles primary, Jay secondary. Solver handles automatically via PB open/close hard constraints + manager avail through 23:00.

## Fixed Schedules (6/29–7/5 week — update the `fx()` block each week)
**This week deviations from standard:** Jay on vacation (Mon only); Myles off Tue/Wed this week instead of Thu/Fri.

| Person | Day | Shift |
|---|---|---|
| Jay | Mon only | solver-placed within [6–15] avail |
| Myles | Mon/Thu/Fri/Sat/Sun | solver-placed within avail (avail extended to 11pm) |
| Bowen | Mon–Fri | 8–4 |
| Gobi | Mon | 4–11 (close) |
| Gobi | Tue | 11–5 |
| Gobi | Wed | 9–5 |
| Gobi | Sat | 8–4 (8am anchor) |
| Gobi | Sun | 3–11 (close) |
| James | Wed | 3–11 (close) |
| James | Sun | 8–4 (8am anchor) |
| Mary | Sat | 3–11 (close — only pinned day) |
| Trinity | Fri | 5–11 (close) |
| Tiffany | Mon | 9–4 |

**8am leader rule:** Mon–Fri = Bowen; Sat = Gobi; Sun = James. One leader always opens at 8am.

---

## Key Constraints
- Every day: ≥1 PB opens (≤10am), ≥1 PB closes (≥10pm)
- 12h close-then-open: next-day start ≥ close-end − 12 (aggregated per person/day/end-time)
- `_trio` (Gobi/James/Trinity): at most 1 closes per day
- Every available person gets ≥1 shift (`zero_pen` = 50 if skipped)
- Max 5 days/week for everyone except Jay
- All shift leaders must work both Tuesday AND Wednesday

---

## Shift Generation Rules
- 15-min grid (ANCH_START: 9–12, 14–18; ANCH_END: 14–18, 20–23)
- 4h min; 8h max PT; 10h max for TEN_HR
- Dead zone: no ends 18:01–19:59 (5pm and 8pm are fine), no ends at 8:15/8:45pm
- No end before 2pm (3pm Sunday)

---

## Solver Settings
- `HiGHS(msg=False, timeLimit=240, gapRel=0.25)`
- Weekly paid hours hard range: `[sum(allowed)+25, sum(allowed)+30]` — no penalty term
- `SCHED_THREADS` env var → parallel B&B (e.g. `SCHED_THREADS=4 python solver2.py`)

---

## Weekly Input Files (update filenames each week)
- `avail_6_29.json` — availability windows per person per day (`"X"` = unavailable, `"any"` = 6–23)
- `reqoff_6_29.json` — request-offs keyed by day name
- `forecast_6_29.json` — `allowed_hours` array + sales figures
