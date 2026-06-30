# Paddock Schedule Solver

MIP (Mixed Integer Programming) weekly shift scheduler for Paddock restaurant.
Uses [PuLP](https://coin-or.github.io/pulp/) + [HiGHS](https://highs.dev/) solver.

---

## Files

| File | Purpose |
|---|---|
| `solver2.py` | **Main solver** — run this each week to generate the schedule |
| `backbone.py` | **Weekly backbone + shared definitions** — fixed shifts, people groups, hour floors, per-person rules. Edit here each week; imported by both the solver and the stress tester |
| `test_protocol.py` | **Stress tester** — randomises req-offs/forecasts to verify the solver handles edge cases |
| `scheduling_rules.md` | **Full business rules** — narrative + checklist for all scheduling constraints |
| `avail.json` | Availability per person per day — overwrite contents each week (filename never changes) |
| `reqoff.json` | Request-offs by day name — overwrite each week |
| `forecast.json` | `{"week_start": "YYYY-MM-DD", "allowed_hours": [...], ...}` — labour budget + the week's date |
| `stress_avail.json` / `stress_reqoff.json` / `stress_forecast.json` | Frozen baseline for the stress tester (not the live week) |
| `CLAUDE.md` | Architecture reference for AI sessions |

---

## Running the scheduler

```bash
# Install dependencies (once)
pip install -r requirements.txt

# Run the solver
python solver2.py

# With parallel branch-and-bound (faster on multi-core machines)
SCHED_THREADS=4 python solver2.py
```

Output: `schedule.json` (full) and `schedule_active.json` (worked days only).
A summary table and rules audit print to the terminal — read it and fix any flagged issues before distributing.

---

## Weekly update checklist

Filenames are stable, so there's nothing to rename and no code path to repoint:

1. Overwrite `avail.json` and `reqoff.json` with the new week's data.
2. Overwrite `forecast.json` (set `week_start` to the new Monday — that's where the date lives now).
3. Update `backbone.py` for any backbone changes (manager schedules, who's fixed where, vacations).
4. Run `python solver2.py` and read the audit output.

---

## Running the stress tester

The stress tester randomises sales forecasts and request-offs and verifies the solver produces a valid schedule for each.

```bash
# Single run (default)
python test_protocol.py

# More runs for thorough stress testing
TEST_RUNS=10 python test_protocol.py
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
