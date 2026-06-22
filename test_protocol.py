#!/usr/bin/env python3
"""
test_protocol.py — Randomized stress-tester for solver2.py

Usage:
    python test_protocol.py                   # 10 runs, seed 42
    TEST_RUNS=25 python test_protocol.py
    TEST_SEED=99 TEST_RUNS=5 python test_protocol.py

What it does:
  - Generates N random (reqoff, forecast) pairs, runs solver2.py for each.
  - 25 request-offs per run: exactly 13 on Fri/Sat/Sun, 12 on Mon-Thu.
  - Sales vary ±random in [-1000, +2500] from the baseline week total,
    scaling allowed_hours proportionally across all 7 days.
  - Availability stays fixed (avail_6_29.json unchanged).
  - Reports: solve status, audit pass/fail, coverage warnings, timing.
  - Writes test_report.json with full per-run details.
"""

import json, os, random, subprocess, sys, tempfile, time
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
SEED    = int(os.environ.get('TEST_SEED',  '42'))
N_RUNS  = int(os.environ.get('TEST_RUNS',   '1'))
BASE_DIR = Path(__file__).resolve().parent

# ── Load base data ───────────────────────────────────────────────────────────
with open(BASE_DIR / 'avail_6_29.json')    as f: AVAIL   = json.load(f)
with open(BASE_DIR / 'reqoff_6_29.json')   as f: BASE_REQOFF   = json.load(f)
with open(BASE_DIR / 'forecast_6_29.json') as f: BASE_FORECAST = json.load(f)

BASE_HOURS = BASE_FORECAST['allowed_hours']          # [Mon..Sun]
BASE_SALES = BASE_FORECAST['forecasted_sales']       # [Mon..Sun]
TOTAL_SALES = sum(BASE_SALES)

DAYS    = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
WEEKEND = ['Fri','Sat','Sun']
WEEKDAY = ['Mon','Tue','Wed','Thu']

# ── Request-off generator ────────────────────────────────────────────────────
def make_reqoff(rng: random.Random) -> dict[str, list[str]]:
    """25 request-offs: exactly 13 on Fri/Sat/Sun, 12 on Mon-Thu.
    Each (person, day) pair is unique; persons may appear on multiple days.
    No one is excluded — including people with fixed backbone shifts.
    This surfaces scenarios where the solver must handle a missing required
    person (infeasibility, coverage gap, etc.) so we can add backup rules.
    Only people already marked 'X' on a day are skipped (already not working).
    """
    buckets: dict[str, set[str]] = {d: set() for d in DAYS}

    def eligible(person: str, day_name: str) -> bool:
        d = DAYS.index(day_name)
        if AVAIL[person][d] == 'X':
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

    fill(WEEKEND, 13)
    fill(WEEKDAY,  12)
    return {d: sorted(buckets[d]) for d in DAYS}


# ── Forecast generator ───────────────────────────────────────────────────────
def make_forecast(rng: random.Random) -> tuple[dict, float]:
    """Scale allowed_hours by a random sales delta in [-1000, +2500].
    Delta is treated as a total-weekly change; each day scales proportionally.
    Returns (forecast_dict, sales_delta).
    """
    delta = rng.uniform(-1000, 2500)
    scale = 1.0 + delta / TOTAL_SALES

    new_hours = [max(55.0, round(h * scale / 0.25) * 0.25) for h in BASE_HOURS]
    new_sales  = [max(0, int(s * scale)) for s in BASE_SALES]

    fc = dict(BASE_FORECAST)
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


# ── Solver runner ────────────────────────────────────────────────────────────
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


# ── Output parser ────────────────────────────────────────────────────────────
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


# ── Main ─────────────────────────────────────────────────────────────────────
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

        # Separate hard failures (constraint violations) from soft hours-under notices
        hard_issues = [i for i in parsed['audit_issues']
                       if not i.startswith('HoursUnder:') and not i.startswith('CovSlack')]
        hours_under = [i for i in parsed['audit_issues'] if i.startswith('HoursUnder:')]

        ok = (parsed['status'] == 'Optimal'
              and parsed['audit'] == 'PASS'
              and not parsed['cov_warnings']
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
            for w in parsed['cov_warnings']:
                print(f"  coverage  : {w}")
            if parsed['zero_shifts']:
                print(f"  zero-shift: {parsed['zero_shifts']} person(s) skipped")
            for line in parsed['stderr_lines']:
                print(f"  stderr    : {line}")
        if hours_under:
            print(f"  hrs-under : {len(hours_under)} person(s) below target (req-offs expected)")
            for iss in hours_under[:4]:
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

    # ── Summary ──────────────────────────────────────────────────────────────
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
            hard = [i for i in r.get('audit_issues',[])
                    if not i.startswith('HoursUnder:') and not i.startswith('CovSlack')]
            if hard: reasons.append(f"hard-audit({len(hard)})")
            if r.get('cov_warnings'):  reasons.append(f"{len(r['cov_warnings'])} cov-warn")
            if r.get('zero_shifts'):   reasons.append(f"{r['zero_shifts']} zeros")
            print(f"  Run {r['run']:02d}: Δsales={r['sales_delta']:+d}  "
                  f"hours={r['total_hours']}  → {', '.join(reasons) or 'unknown'}")

    # ── Write report ─────────────────────────────────────────────────────────
    report = BASE_DIR / 'test_report.json'
    with open(report, 'w') as f:
        json.dump({'seed': SEED, 'n_runs': N_RUNS, 'results': all_results}, f, indent=2)
    print(f"\nReport → {report}")

    # ── Clean up temp dir ─────────────────────────────────────────────────────
    tmp = BASE_DIR / '_test_tmp'
    if tmp.exists() and not any(tmp.iterdir()):
        tmp.rmdir()


if __name__ == '__main__':
    main()
