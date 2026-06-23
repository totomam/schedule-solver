# Paddock Schedule Solver

MIP (Mixed Integer Programming) weekly shift scheduler for Paddock restaurant.
Uses [PuLP](https://coin-or.github.io/pulp/) + [HiGHS](https://highs.dev/) solver.

---

## Files

| File | Purpose |
|---|---|
| `solver2.py` | **Main solver** — run this each week to generate the schedule |
| `test_protocol.py` | **Stress tester** — randomises req-offs across 20 runs to verify the solver handles edge cases |
| `scheduling_rules.md` | **Full business rules** — narrative + checklist for all scheduling constraints |
| `avail_6_29.json` | Availability per person per day (update filename/content each week) |
| `reqoff_6_29.json` | Request-offs by day name (update each week) |
| `forecast_6_29.json` | `{"allowed_hours": [...]}` — labour budget per day (update each week) |
| `CLAUDE.md` | Architecture reference for AI sessions |
| `ai_reference.md` | Quick-reference sheet for AI sessions (people groups, hour targets, constraints) |

---

## Running the scheduler

```bash
# Install dependencies (once)
pip install pulp highspy openpyxl

# Run the solver
python solver2.py

# With parallel branch-and-bound (faster on multi-core machines)
SCHED_THREADS=4 python solver2.py
```

Output: `schedule.json` (full) and `schedule_active.json` (worked days only).
A summary table and rules audit print to the terminal — read it and fix any flagged issues before distributing.

---

## Weekly update checklist

1. Copy last week's `avail_*.json`, `reqoff_*.json`, `forecast_*.json` → rename with the new Mon date.
2. Update availability and req-off data for the new week.
3. Update the `fx()` backbone block near the top of `solver2.py` for any manager schedule changes.
4. Update the filename references inside `solver2.py` (search for `avail_6_29`).
5. Run `python solver2.py` and read the audit output.

---

## Running the stress tester

The stress tester randomises sales forecasts and request-offs across 20 scenarios and verifies the solver produces a valid schedule for each.

```bash
# 20 runs (default)
TEST_RUNS=20 python test_protocol.py

# Faster run with relaxed hours-under check
FULL_HOURS_UNDER=0 TEST_RUNS=10 python test_protocol.py
```

Results are written to `test_report.json`. Each run prints `[OK]` or `[FAIL]` with a brief reason.

---

## Scheduling rules

See [`scheduling_rules.md`](scheduling_rules.md) for the full set of business rules including:
- Coverage targets by meal period and day
- Leader open/close requirements (≥1 leader/manager opens ≤9am; ≥1 closes ≥10pm)
- 12-hour close-then-open rest rule
- Per-person constraints (Adam always ends 11pm, Molly never past 5pm, etc.)
- Hours targets by role

---

## Architecture notes

See [`CLAUDE.md`](CLAUDE.md) for solver design decisions (soft constraints, pre-filtered variable lists, objective weights, etc.).
