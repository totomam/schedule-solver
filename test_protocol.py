#!/usr/bin/env python3
"""
test_protocol.py — Randomized stress-tester for solver2.py

Usage:
    python test_protocol.py                   # 10 runs, seed 42
    TEST_RUNS=25 python test_protocol.py
    TEST_SEED=99 TEST_RUNS=5 python test_protocol.py

What it does:
  - Generates N random (reqoff, forecast) pairs, runs solver2.py for each.
  - 10–25 request-offs per run (random), split 50/50 between Fri/Sat/Sun and Mon-Thu.
  - Sales vary ±random in [-1000, +2500] from the baseline week total,
    scaling allowed_hours proportionally across all 7 days.
  - Availability stays fixed (avail_6_29.json unchanged).
  - Reports: solve status, audit pass/fail, coverage warnings, timing.
  - Writes test_report.json with full per-run details.
"""

import json, os, random, re, subprocess, sys, tempfile, time
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────────────
SEED    = int(os.environ.get('TEST_SEED',  str(random.randint(0, 2**31 - 1))))
N_RUNS  = int(os.environ.get('TEST_RUNS',   '1'))
BASE_DIR = Path(__file__).resolve().parent

# ── Load base data ────────────────────────────────────────────────────────────────────────
with open(BASE_DIR / 'avail_6_29.json')    as f: AVAIL   = json.load(f)
with open(BASE_DIR / 'reqoff_6_29.json')   as f: BASE_REQOFF   = json.load(f)
with open(BASE_DIR / 'forecast_6_29.json') as f: BASE_FORECAST = json.load(f)

BASE_HOURS = BASE_FORECAST['allowed_hours']          # [Mon..Sun]
BASE_SALES = BASE_FORECAST['forecasted_sales']       # [Mon..Sun]
TOTAL_SALES = sum(BASE_SALES)

DAYS    = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
WEEKEND = ['Fri','Sat','Sun']
WEEKDAY = ['Mon','Tue','Wed','Thu']

_JAY   = 'John Martin (Jay)'
_MYLES = 'Myles Palmer'
# Shift leaders — not managers
_LEADERS = {'Bowen Benedict', 'James Baker', 'Trinity Stringer', 'Gobi Weathers', 'Mary Dean'}
# FT employees + shift leaders: missing their hours floor is a hard scheduling failure
# (unless req-offs made it mathematically impossible to reach the target)
_FT_AND_LEADERS = _LEADERS | {
    'Adam Van Bogaert', 'Mason Doyle', 'Michael Calderon', 'Molly Summers',
    'Noah Hiner', 'Ava Shade', 'Izzy Simpson', 'Remi Sullinger', 'Reilly Weakley',
}
_PB_ALL = {_JAY, _MYLES} | _LEADERS

# Backbone shifts (mirrors solver2.py) — needed to know which PB members can actually
# open (start ≤ 10am) or close (end ≥ 10pm) on each day once backbone locks them in.
# Format: (person, day_index 0=Mon…6=Sun) → (start_h, end_h)
_BACKBONE_SHIFTS: dict[tuple, tuple] = {
    (_JAY,   0): ( 6, 15),  (_JAY,   3): (10, 20),  (_JAY,   4): (10, 20),
    (_JAY,   5): (10, 20),  (_JAY,   6): (11, 17),
    (_MYLES, 0): (12, 21),  (_MYLES, 1): (11, 20),  (_MYLES, 2): (11, 20),
    (_MYLES, 5): (12, 21),  (_MYLES, 6): (12, 21),
    ('Bowen Benedict',   0): (8, 16),  ('Bowen Benedict',   1): (8, 16),
    ('Bowen Benedict',   2): (8, 16),  ('Bowen Benedict',   3): (8, 16),
    ('Bowen Benedict',   4): (8, 16),
    ('Gobi Weathers',    0): (16, 23), ('Gobi Weathers',    1): (11, 17),
    ('Gobi Weathers',    2): ( 9, 17), ('Gobi Weathers',    5): ( 8, 16),
    ('Gobi Weathers',    6): (15, 23),
    ('Mary Dean',        5): (15, 23),
    ('James Baker',      2): (15, 23), ('James Baker',      6): ( 8, 16),
    ('Trinity Stringer', 4): (17, 23),
}

def _pb_can_open_day(person: str, day_idx: int) -> bool:
    """True if this PB member has a BACKBONE shift starting ≤9am on this day,
    and the previous-day backbone (if any) doesn't close late (12h rule).
    Non-backbone shifts are excluded — solver may assign them at any time.
    Jay is excluded per scheduling rules.
    """
    if person == _JAY:
        return False
    bk = _BACKBONE_SHIFTS.get((person, day_idx))
    if not bk or bk[0] > 9:
        return False
    prev_bk = _BACKBONE_SHIFTS.get((person, (day_idx - 1) % 7))
    if prev_bk and prev_bk[1] >= 22:
        return False
    return True

def _pb_can_close_day(person: str, day_idx: int) -> bool:
    """True if this PB member could have an end ≥ 10pm (22:00) on this day."""
    w = AVAIL[person][day_idx]
    if w == 'X':
        return False
    bk = _BACKBONE_SHIFTS.get((person, day_idx))
    if bk:
        return bk[1] >= 22
    hi = 23.0 if w in ('any', 'open') else float(w[1])
    return hi >= 22.0

# Precomputed: which PB members can open / close on each day of the week
_PB_VIABLE_OPENERS: dict[str, list] = {
    day: [p for p in _PB_ALL if _pb_can_open_day(p, d)] for d, day in enumerate(DAYS)
}
_PB_VIABLE_CLOSERS: dict[str, list] = {
    day: [p for p in _PB_ALL if _pb_can_close_day(p, d)] for d, day in enumerate(DAYS)
}

_TEN_HR = _PB_ALL | {
    'Adam Van Bogaert', 'Mason Doyle', 'Michael Calderon', 'Molly Summers',
    'Noah Hiner', 'Ava Shade', 'Remi Sullinger', 'Izzy Simpson', 'Zac Duffy', 'Kara Thompson',
}

def _max_achievable_raw(person: str, reqoff: dict) -> float:
    """Max raw hours a person could work this week given their avail windows and req-offs."""
    max_shift = 10.0 if person in _TEN_HR else 8.0
    # Per-person hard caps that reduce the effective max shift regardless of avail window
    if person == 'Molly Summers':
        max_shift = min(max_shift, 8.0)  # never past 5pm; earliest start 9am → 8h ceiling
    day_maxes = []
    for d, day in enumerate(DAYS):
        w = AVAIL[person][d]
        if w == 'X' or person in reqoff.get(day, []):
            continue
        if w in ('any', 'open'):
            lo, hi = 6.0, 23.0
        else:
            lo, hi = float(w[0]), float(w[1])
        # Apply solver's per-person floor/ceiling rules
        if person not in (_JAY, 'Bowen Benedict'):
            lo = max(lo, 9.0)   # 9am start floor for most people
        if person == 'Molly Summers':
            hi = min(hi, 17.0)
        window = max(0.0, hi - lo)
        day_maxes.append(min(window, max_shift))
    day_maxes.sort(reverse=True)
    limit = 7 if person == _JAY else 5  # Jay has no 5-day cap
    return sum(day_maxes[:limit])

def _compute_budget_constrained(audit_issues: list, var) -> bool:
    """True if total FT/SL raw-hour shortfall exceeds paid budget headroom (+30 ceiling)."""
    budget_headroom = 30.0 - float(var or 0)
    total = 0.0
    for iss in audit_issues:
        if not iss.startswith('HoursUnder:'):
            continue
        if not any(iss.startswith(f'HoursUnder: {n}') for n in _FT_AND_LEADERS):
            continue
        m_a = re.search(r'(\d+\.?\d*)h actual', iss)
        m_t = re.search(r'target ≥(\d+\.?\d*)h', iss)
        if m_a and m_t:
            total += max(0.0, float(m_t.group(1)) - float(m_a.group(1)))
    return total > budget_headroom

def _ft_leader_hu_is_hard(issue: str, reqoff: dict, budget_constrained: bool = False) -> bool:
    """Return True if a FT/leader HoursUnder was avoidable — i.e. a hard scheduling failure."""
    if not issue.startswith('HoursUnder:'):
        return False
    matched = next((n for n in _FT_AND_LEADERS if issue.startswith(f'HoursUnder: {n}')), None)
    if matched is None:
        return False
    m_actual = re.search(r'(\d+\.?\d*)h actual', issue)
    m_target = re.search(r'target ≥(\d+\.?\d*)h', issue)
    if not m_target:
        return True  # can't parse target — treat as hard
    target = float(m_target.group(1))
    # ≤0.5h shortfall: within grid/structural tolerance (12h rule, shift-length grid)
    if m_actual and (target - float(m_actual.group(1))) <= 0.5:
        return False
    # Budget ceiling (+30) prevented full satisfaction — not a solver failure
    if budget_constrained:
        return False
    # If max possible hours >= target, the shortfall was avoidable → hard failure
    return _max_achievable_raw(matched, reqoff) >= target

# ── Request-off generator ─────────────────────────────────────────────────────────────────────────
def make_reqoff(rng: random.Random) -> dict[str, list[str]]:
    """10–25 request-offs (random), split 50/50 between Fri/Sat/Sun and Mon-Thu.
    Each (person, day) pair is unique; persons may appear on multiple days.
    No one is excluded — including people with fixed backbone shifts.
    Only people already marked 'X' on a day are skipped (already not working).

    Two structural guarantees are enforced:
    1. If both Jay and Myles are req'd off the same day, no shift leader can also
       req off that day (ensures ≥1 PB member available).
    2. The last viable PB opener (start ≤ 10am) or closer (end ≥ 10pm) for a given
       day can never be req'd off — protecting structurally sole-critical people
       (e.g. Gobi as the only Sunday closer, Mary Dean as the only Saturday closer,
       James Baker as the only Sunday opener given current avail + backbone).
    """
    buckets: dict[str, set[str]] = {d: set() for d in DAYS}

    def eligible(person: str, day_name: str) -> bool:
        d = DAYS.index(day_name)
        if AVAIL[person][d] == 'X':
            return False
        # Block shift leaders on days where both managers are already off
        if person in _LEADERS:
            if _JAY in buckets[day_name] and _MYLES in buckets[day_name]:
                return False
        # Never req-off a PB member if they are the last viable opener or closer for the day
        if person in _PB_ALL:
            remaining_closers = [p for p in _PB_VIABLE_CLOSERS[day_name]
                                 if p != person and p not in buckets[day_name]]
            if not remaining_closers:
                return False
            remaining_openers = [p for p in _PB_VIABLE_OPENERS[day_name]
                                 if p != person and p not in buckets[day_name]]
            if not remaining_openers:
                return False
        return True

    def fill(day_pool: list[str], target: int) -> None:
        placed = 0
        attempts = 0
        while placed < target:
            attempts += 1
            if attempts > 50_000:
                break  # safety valve — shouldn't trigger with this roster size
            day = rng.choice(day_pool)
            candidates = [p for p in AVAIL if eligible(p, day) and p not in buckets[day]]
            if not candidates:
                continue
            buckets[day].add(rng.choice(candidates))
            placed += 1

    total      = rng.randint(10, 25)
    weekend_n  = total // 2
    weekday_n  = total - weekend_n
    fill(WEEKEND, weekend_n)
    fill(WEEKDAY,  weekday_n)

    # Post-process: if both managers ended up off the same day, remove any leaders
    # that slipped through (edge case when leader was added before second manager)
    for day in DAYS:
        if _JAY in buckets[day] and _MYLES in buckets[day]:
            buckets[day] = {p for p in buckets[day] if p not in _LEADERS}

    return {d: sorted(buckets[d]) for d in DAYS}


# ── Forecast generator ─────────────────────────────────────────────────────────────────────────
def make_forecast(rng: random.Random) -> tuple[dict, float]:
    """Scale allowed_hours by a random sales delta in [-1000, +2500].
    Delta is treated as a total-weekly change; each day scales proportionally.
    Returns (forecast_dict, sales_delta).
    """
    delta = rng.uniform(-1000, 2500)
    scale = 1.0 + delta / TOTAL_SALES

    new_hours = [max(55.0, round(h * scale / 0.25) * 0.25) for h in BASE_HOURS]
    new_sales  = [max(0, int(s * scale)) for s in BASE_SALES]

    fc = {k: v for k, v in BASE_FORECAST.items() if k != 'week_start'}
    fc['allowed_hours']     = new_hours
    fc['forecasted_sales']  = new_sales
    # Sub-components scaled proportionally so the Excel summary still sums correctly
    for key in ('inline_sales', 'digital_sales'):
        if key in fc:
            fc[key] = [max(0, int(v * scale)) for v in fc[key]]
    for key in ('cap_allowed', 'inline_sales_allowed', 'digital_sales_allowed'):
        if key in fc:
            fc[key] = [max(0.0, round(v * scale / 0.25) * 0.25) for v in fc[key]]
    return fc, delta


# ── Solver runner ────────────────────────────────────────────────────────────────────────────
def run_solver(reqoff: dict, forecast: dict, run_id: int) -> tuple[int, str, str, float]:
    """Write temp files, run solver2.py, return (returncode, stdout, stderr, elapsed_s)."""
    tmp = BASE_DIR / '_test_tmp'
    tmp.mkdir(exist_ok=True)

    reqoff_path   = tmp / f'reqoff_{run_id}.json'
    forecast_path = tmp / f'forecast_{run_id}.json'
    out_path      = tmp / f'schedule_{run_id}.json'

    reqoff_path.write_text(json.dumps(reqoff,   indent=2))
    forecast_path.write_text(json.dumps(forecast, indent=2))

    env = os.environ.copy()
    env['SCHED_AVAIL']    = str(BASE_DIR / 'avail_6_29.json')
    env['SCHED_REQOFF']   = str(reqoff_path)
    env['SCHED_FORECAST'] = str(forecast_path)
    env['SCHED_OUT']      = str(out_path)

    t0 = time.time()
    result = subprocess.run(
        [sys.executable, str(BASE_DIR / 'solver2.py')],
        capture_output=True, text=True,
        cwd=str(BASE_DIR),
        timeout=360,
        env=env,
    )
    elapsed = time.time() - t0

    # Clean up temp files (xlsx written if openpyxl installed)
    stem = out_path.stem
    for p in [reqoff_path, forecast_path, out_path,
              out_path.parent / f'{stem}_active.json',
              out_path.parent / f'{stem}.xlsx']:
        if p.exists():
            p.unlink()

    return result.returncode, result.stdout, result.stderr, elapsed


# ── Output parser ────────────────────────────────────────────────────────────────────────────
def parse_output(stdout: str, stderr: str, returncode: int) -> dict:
    """Extract key metrics from solver stdout."""
    result = {
        'status':         'UNKNOWN',
        'audit':          'UNKNOWN',
        'audit_issues':   [],
        'cov_warnings':   [],
        'zero_shifts':    0,
        'paid_total':     None,
        'var':            None,
        'stderr_lines':   [],
    }

    lines = stdout.splitlines()

    for line in lines:
        # e.g. "Status: Optimal | paid 730.5 | var +0.0 | zeros 0"
        if line.startswith('Status:'):
            parts = line.split('|')
            result['status'] = parts[0].split(':', 1)[1].strip()
            for part in parts[1:]:
                k, _, v = part.strip().partition(' ')
                if k == 'paid':
                    try: result['paid_total'] = float(v)
                    except ValueError: pass
                elif k == 'var':
                    try: result['var'] = float(v)
                    except ValueError: pass
                elif k == 'zeros':
                    try: result['zero_shifts'] = int(v)
                    except ValueError: pass

        # e.g. "WARNING: 3 coverage slack(s) nonzero: ..."
        if line.startswith('WARNING:'):
            result['cov_warnings'].append(line.strip())

        # e.g. "Audit: PASS" or "Audit: 2 issue(s):"
        if line.startswith('Audit:'):
            tail = line.split(':', 1)[1].strip()
            result['audit'] = 'PASS' if tail == 'PASS' else f'FAIL ({tail})'

        # Audit detail lines (indented)
        if result['audit'].startswith('FAIL') and line.startswith('  ') and line.strip():
            result['audit_issues'].append(line.strip())

    if returncode != 0:
        result['status'] = f'ERROR (rc={returncode})'

    if stderr:
        result['stderr_lines'] = [l for l in stderr.splitlines() if l.strip()][:5]

    return result


# ── Main ─────────────────────────────────────────────────────────────────────────────────
def main() -> None:
    master_rng = random.Random(SEED)
    print(f"=== Solver Test Protocol  seed={SEED}  runs={N_RUNS} ===\n")

    all_results = []
    run_seeds = [master_rng.randint(0, 2**31) for _ in range(N_RUNS)]

    for run_id in range(N_RUNS):
        run_seed = run_seeds[run_id]
        rng = random.Random(run_seed)

        reqoff   = make_reqoff(rng)
        forecast, sales_delta = make_forecast(rng)

        total_req   = sum(len(v) for v in reqoff.values())
        weekend_req = sum(len(reqoff[d]) for d in WEEKEND)
        total_hours = sum(forecast['allowed_hours'])

        label = (f"Run {run_id+1:02d}/{N_RUNS}  "
                 f"Δsales={sales_delta:+.0f}  "
                 f"hours={total_hours:.1f}  "
                 f"reqoff={total_req} ({weekend_req} Fri-Sun)")
        print(label + " ... ", end='', flush=True)

        try:
            rc, stdout, stderr, elapsed = run_solver(reqoff, forecast, run_id)
        except subprocess.TimeoutExpired:
            print("TIMEOUT")
            all_results.append({'run': run_id+1, 'status': 'TIMEOUT',
                                 'sales_delta': round(sales_delta),
                                 'total_hours': round(total_hours, 1),
                                 'elapsed': 360})
            continue

        parsed = parse_output(stdout, stderr, rc)

        # Separate hard failures from soft informational notices.
        # FT/leader HoursUnder is hard only when:
        #   - shortfall > 0.5h (not grid/structural rounding)
        #   - budget not constrained (total FT/SL shortfall fits within the +30 headroom)
        #   - req-offs didn't make the target unreachable
        budget_constrained = _compute_budget_constrained(parsed['audit_issues'], parsed['var'])
        hard_issues = [i for i in parsed['audit_issues']
                       if (not i.startswith('HoursUnder:') and not i.startswith('CovSlack'))
                       or _ft_leader_hu_is_hard(i, reqoff, budget_constrained)]
        hours_under = [i for i in parsed['audit_issues']
                       if i.startswith('HoursUnder:') and not _ft_leader_hu_is_hard(i, reqoff, budget_constrained)]

        ok = (parsed['status'] == 'Optimal'
              and not hard_issues
              and parsed['zero_shifts'] == 0)

        tag = 'OK' if ok else 'FAIL'
        print(f"{elapsed:.1f}s  [{tag}]")

        if not ok:
            if parsed['status'] != 'Optimal':
                print(f"  status    : {parsed['status']}")
            if hard_issues:
                print(f"  audit     : FAIL ({len(hard_issues)} hard issue(s):)")
                for iss in hard_issues[:6]:
                    print(f"              {iss}")
            if parsed['zero_shifts']:
                print(f"  zero-shift: {parsed['zero_shifts']} person(s) skipped")
            for line in parsed['stderr_lines']:
                print(f"  stderr    : {line}")
        for w in parsed['cov_warnings']:
            print(f"  coverage  : {w}")
        if hours_under:
            full = os.environ.get('FULL_HOURS_UNDER')
            limit = None if full else 4
            print(f"  hrs-under : {len(hours_under)} person(s) below target (req-offs expected)")
            for iss in hours_under[:limit]:
                m_a = __import__('re').search(r'(\d+\.?\d*)h actual', iss)
                m_t = __import__('re').search(r'target ≥(\d+\.?\d*)h', iss)
                shortfall = f"  [{float(m_t.group(1))-float(m_a.group(1)):.1f}h short]" if m_a and m_t else ''
                print(f"              {iss}{shortfall}")

        record = {
            'run':          run_id + 1,
            'seed':         run_seed,
            'sales_delta':  round(sales_delta),
            'total_hours':  round(total_hours, 1),
            'total_reqoff': total_req,
            'weekend_reqoff': weekend_req,
            'reqoff_detail': {d: reqoff[d] for d in DAYS if reqoff[d]},
            'solve_status': parsed['status'],
            'audit':        parsed['audit'],
            'audit_issues': parsed['audit_issues'],
            'cov_warnings': parsed['cov_warnings'],
            'zero_shifts':  parsed['zero_shifts'],
            'paid_total':   parsed['paid_total'],
            'var':          parsed['var'],
            'elapsed':      round(elapsed, 1),
            'pass':         ok,
        }
        all_results.append(record)

    # ── Summary ────────────────────────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"Summary: {N_RUNS} run(s)")

    passed  = sum(1 for r in all_results if r.get('pass'))
    failed  = [r for r in all_results if not r.get('pass')]
    elapsed = [r['elapsed'] for r in all_results if 'elapsed' in r]
    print(f"  Passed : {passed}/{N_RUNS}")
    print(f"  Failed : {len(failed)}")
    if elapsed:
        print(f"  Avg time: {sum(elapsed)/len(elapsed):.1f}s  "
              f"max={max(elapsed):.1f}s  min={min(elapsed):.1f}s")

    if failed:
        print(f"\nFailed runs:")
        for r in failed:
            reasons = []
            if r.get('solve_status','') != 'Optimal': reasons.append(r['solve_status'])
            stored_reqoff = {d: r['reqoff_detail'].get(d, []) for d in DAYS}
            bc = _compute_budget_constrained(r.get('audit_issues', []), r.get('var', 0))
            hard = [i for i in r.get('audit_issues',[])
                    if (not i.startswith('HoursUnder:') and not i.startswith('CovSlack'))
                    or _ft_leader_hu_is_hard(i, stored_reqoff, bc)]
            if hard: reasons.append(f"hard-audit({len(hard)})")
            if r.get('cov_warnings'):  reasons.append(f"{len(r['cov_warnings'])} cov-warn")
            if r.get('zero_shifts'):   reasons.append(f"{r['zero_shifts']} zeros")
            print(f"  Run {r['run']:02d}: Δsales={r['sales_delta']:+d}  "
                  f"hours={r['total_hours']}  → {', '.join(reasons) or 'unknown'}")

    # ── Write report ───────────────────────────────────────────────────────────────────────────
    report = BASE_DIR / 'test_report.json'
    with open(report, 'w') as f:
        json.dump({'seed': SEED, 'n_runs': N_RUNS, 'results': all_results}, f, indent=2)
    print(f"\nReport → {report}")

    # ── Clean up temp dir ─────────────────────────────────────────────────────────────────────────
    tmp = BASE_DIR / '_test_tmp'
    if tmp.exists() and not any(tmp.iterdir()):
        tmp.rmdir()


if __name__ == '__main__':
    main()
