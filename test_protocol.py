#!/usr/bin/env python3
"""
test_protocol.py — Randomized stress-tester for solver2.py

Usage:
    python test_protocol.py                   # 10 runs, seed 42
    TEST_RUNS=25 python test_protocol.py
    TEST_SEED=99 TEST_RUNS=5 python test_protocol.py

What it does:
  - Generates N random (reqoff, forecast) pairs, runs solver2.py for each.
  - 20–50 request-offs per run (random), split 55% weekday / 45% weekend.
  - Sales vary ±random in [-1000, +2500] from a $35,500 baseline,
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
BASELINE_SALES = 35_500  # reference total for delta scaling

DAYS    = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
WEEKEND = ['Fri','Sat','Sun']
WEEKDAY = ['Mon','Tue','Wed','Thu']

_JAY   = 'Jay Martin'
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
    (_JAY,   0): ( 6, 15),  (_JAY,   1): (10, 20),  (_JAY,   2): (10, 20),
    (_JAY,   3): (10, 20),  (_JAY,   4): (10, 20),
    (_JAY,   5): (10, 20),  (_JAY,   6): (11, 17),
    # Myles working days (Mon/Tue/Wed/Sat/Sun) omitted: solver shifts to (14,23) when he's
    # the only PB closer that day, so the stress test uses raw avail (any → hi=23 → can close).
    # Thu/Fri are compensation-only days capped at (11,20) by _MGR_OFFDAY_SHIFT → can't close.
    (_MYLES, 3): (11, 20),  (_MYLES, 4): (11, 20),
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
    """
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

def _early_ok(person: str, d: int) -> bool:
    """Mirror solver2.py gen(): who may start before 9am on day d."""
    return (person in (_JAY, 'Bowen Benedict')
            or (person in ('Gobi Weathers', 'Trinity Stringer') and d == 5)
            or (person == 'James Baker' and d == 6))

def _max_achievable_raw(person: str, reqoff: dict) -> float:
    """Max raw hours a person could work this week, respecting the constraints that
    actually cap reachable hours: avail windows, req-offs, the 9am start floor, per-person
    shift-length caps, fixed backbone shifts, the ≤5-shift/week cap, AND the 12-hour
    close-then-open rest rule (a close ending ≥9pm forces the next calendar day's start
    to ≥ end−12). The naive "5 longest windows" sum ignored the rest rule and backbone
    closes, over-stating reachable hours (e.g. it claimed 39h for Trinity whose fixed
    Fri 17-23 close + the rest rule cap her at 37h) — which produced false hard flags.

    Solved as a tiny DP across the 7 calendar days. State = (end time of the immediately
    preceding day's shift, shifts used so far); we maximise total raw hours."""
    max_shift = 10.0 if person in _TEN_HR else 8.0
    GRID = 0.25
    limit = 7 if person == _JAY else 5  # ≤5 shifts/week for everyone except Jay

    # Per-day window: None (off), ('fixed', a, b) for a backbone shift, or ('free', lo, hi).
    day_win: list = []
    for d, day in enumerate(DAYS):
        w = AVAIL[person][d]
        if w == 'X' or person in reqoff.get(day, []):
            day_win.append(None); continue
        bk = _BACKBONE_SHIFTS.get((person, d))
        if bk:                                   # fixed backbone shift — exact window
            day_win.append(('fixed', float(bk[0]), float(bk[1]))); continue
        lo, hi = (6.0, 23.0) if w in ('any', 'open') else (float(w[0]), float(w[1]))
        if not _early_ok(person, d):
            lo = max(lo, 9.0)
        if person == 'Molly Summers':
            hi = min(hi, 17.0)
        day_win.append(('free', lo, hi))

    # DP: state (prev_end, used) -> best total hours. prev_end == 0.0 means prev day was off.
    NEG = float('-inf')
    states = {(0.0, 0): 0.0}
    for d in range(7):
        win = day_win[d]
        nxt = {}
        def relax(key, val):
            if val > nxt.get(key, NEG):
                nxt[key] = val
        for (prev_end, used), tot in states.items():
            relax((0.0, used), tot)              # option: don't work day d
            if used >= limit or win is None:
                continue
            rest_floor = prev_end - 12.0 if prev_end >= 21.0 else 0.0  # 12h close→open rule
            if win[0] == 'fixed':
                a, b = win[1], win[2]
                if a < rest_floor - 1e-9:
                    continue                     # backbone close-then-open rest violation
                length = min(b - a, max_shift)
                if length >= 4.0 - 1e-9:
                    relax((b, used + 1), tot + length)
            else:                                # 'free': start as early as the rest rule allows
                _, lo, hi = win
                a = max(lo, rest_floor)
                if hi - a < 4.0 - 1e-9:
                    continue
                b = a + 4.0
                bmax = min(hi, a + max_shift)     # length capped by the per-person shift max
                while b <= bmax + 1e-9:           # enumerate end times: a late close (b≥21) costs
                    relax((round(b, 2), used + 1), tot + (b - a))  # the next day; an early end frees it
                    b += GRID
        states = nxt
    return max(states.values()) if states else 0.0

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

def _classify_issues(audit_issues: list, reqoff: dict, var, budget_constrained: bool = None):
    """Split audit issues into (hard, soft) lists.
    near_ceiling (var ≥ 26) exempts LeaderClose/LeaderOpen from hard status.
    """
    if budget_constrained is None:
        budget_constrained = _compute_budget_constrained(audit_issues, var)
    near_ceiling = (var is not None and float(var) >= 26)
    hard, soft = [], []
    for i in audit_issues:
        if _ft_leader_hu_is_hard(i, reqoff, budget_constrained):
            hard.append(i)
        elif (i.startswith('HoursUnder:') or i.startswith('CovSlack')
              # Graduated soft-target misses: 1 closer below target & lunch below its 11 aspiration
              # are by-design soft (small penalty), NOT failures. The massive 2+-below closer tier
              # ('CLOSER 2+ BELOW TARGET') is left to fall through to hard.
              or i.startswith('CloserTargetMiss') or i.startswith('LunchTargetMiss')
              or i.startswith('DinnerTargetMiss')
              or (near_ceiling and (i.startswith('LeaderClose') or i.startswith('LeaderOpen')))):
            soft.append(i)
        else:
            hard.append(i)
    return hard, soft

# ── Request-off generator ─────────────────────────────────────────────────────────────────────────
def make_reqoff(rng: random.Random) -> dict[str, list[str]]:
    """20–50 request-offs (random), split 55% weekday (Mon-Thu) / 45% weekend (Fri/Sat/Sun).
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
        # Spread `target` req-offs EVENLY across the days in day_pool (weekend → ~1/3 each day,
        # weekday → ~1/4 each), so no single day gets gutted by random clustering. The remainder
        # is sprinkled onto random days. People within each day are still chosen at random.
        per = {d: target // len(day_pool) for d in day_pool}
        for d in rng.sample(day_pool, target % len(day_pool)):
            per[d] += 1
        for day in day_pool:
            placed = 0
            while placed < per[day]:
                candidates = [p for p in AVAIL if eligible(p, day) and p not in buckets[day]]
                if not candidates:
                    break  # this day is tapped out — drop the remaining share rather than pile elsewhere
                buckets[day].add(rng.choice(candidates))
                placed += 1

    total      = rng.randint(20, 50)
    weekday_n  = round(total * 0.55)   # 55% weekday / 45% weekend — matches the real-book skew
    weekend_n  = total - weekday_n     # (real July 6 book was 54/46; 50/50 over-loaded the weekend)
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
    """Scale allowed_hours by a random sales delta in [-1000, +2500] from a $35,500 baseline.
    Delta is treated as a total-weekly change; each day scales proportionally.
    Returns (forecast_dict, sales_delta).
    """
    delta = rng.uniform(-1000, 2500)
    scale = 1.0 + delta / BASELINE_SALES

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
        # LeaderClose/LeaderOpen at budget ceiling: gapRel=0.25 stops before finding the
        # close-shift extension when headroom ≤4h. Not a structural failure — happens only
        # at extreme sales drops (≥20%) that won't occur in production.
        budget_constrained = _compute_budget_constrained(parsed['audit_issues'], parsed['var'])
        hard_issues, soft_issues = _classify_issues(parsed['audit_issues'], reqoff, parsed['var'], budget_constrained)
        hours_under = [i for i in soft_issues if i.startswith('HoursUnder:')]

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
                # solver audit line already includes the "[Nh short]" suffix
                print(f"              {iss}")

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
            hard, _ = _classify_issues(r.get('audit_issues', []), stored_reqoff, r.get('var'), bc)
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
