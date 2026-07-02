"""Shared weekly backbone — single source of truth for solver2.py AND test_protocol.py.

The backbone changes every week. Editing it here (instead of the old hand-copied
`fx()` calls in solver2.py plus a duplicate dict in test_protocol.py) means the
solver and the stress-test's reachability math can never drift apart.

Day index: 0=Mon, 1=Tue, ... 6=Sun.

What's shared vs. local:
  • STATIC_BACKBONE (non-manager fixed shifts) is imported by BOTH the solver and
    the test, so the test always mirrors exactly what the solver locks in.
  • The manager maps (Jay/Myles) are imported by the SOLVER only. The test models
    the managers' DYNAMIC behaviour (open/close backstop selection) with its own
    local approximation — see _BACKBONE_SHIFTS in test_protocol.py.
"""

# ── People groups (shared so the solver and the stress test can't drift apart) ──
# Shift leaders + managers.
PB = {'Jay Martin', 'Myles Palmer', 'Bowen Benedict', 'James Baker',
      'Trinity Stringer', 'Gobi Weathers', 'Mary Dean'}
# Managers: paid = raw hours, no 0.5h unpaid-break deduction.
NO_BREAK = {'Jay Martin', 'Myles Palmer'}
# Full-time non-leaders (33h+ target). NOTE: being full-time does NOT by itself mean
# 10h-eligible — the prep full-timers below leave by ~5pm and so top out at 8h. See TEN_HR.
FT_NONLEADER = {'Adam Van Bogaert', 'Mason Doyle', 'Michael Calderon', 'Molly Summers',
                'Noah Hiner', 'Ava Shade', 'Izzy Simpson', 'Remi Sullinger', 'Reilly Weakley'}
# 10-hour-shift eligible: leaders/managers + the full-timers who can work late
# (Adam, Mason, Ava, Remi, Izzy) + Zac & Kara. Deliberately EXCLUDES the prep full-timers
# (Michael Calderon, Noah Hiner, Molly Summers, Reilly Weakley): they aren't available past
# ~5pm, so a 9am start already caps them at 8h.
TEN_HR = PB | {'Adam Van Bogaert', 'Mason Doyle', 'Ava Shade', 'Remi Sullinger',
               'Izzy Simpson', 'Zac Duffy', 'Kara Thompson'}

# Non-manager backbone: {(person, day): (start_h, end_h)} — fixed shifts for the week.
STATIC_BACKBONE = {
    **{('Bowen Benedict', d): (8, 16) for d in range(5)},
    # Mon trimmed to end 8:30p (not her usual 11p close) so the 12h rest rule doesn't push
    # her Tue start past 10a — she needs to leave by 2pm Tue this week (7/13-7/19 request).
    # Another PB member (Mary Dean/James Baker) covers Monday's close instead; the hard
    # >=1-PB-closer/day floor forces the solver to pick one of them automatically.
    ('Gobi Weathers', 0): (16, 20.5),
    ('Gobi Weathers', 1): (10, 14),   # Tue: needs to leave by 2pm this week (see Mon note above)
    ('Gobi Weathers', 2): (9, 17),
    ('Gobi Weathers', 5): (9, 17),
    ('Gobi Weathers', 6): (15, 23),
    ('Mary Dean', 5): (15, 23),
    ('Tiffany Huffman', 0): (9, 16),
    ('Trinity Stringer', 4): (17, 23),
    ('Zac Duffy', 6): (9, 17),        # Zac opens Sunday 9-5 (8h, longest valid 9-start under his 10h cap)
}

# Manager standard / fallback candidate shifts (the SOLVER picks among these dynamically:
# Jay falls back to the OPEN variant when no other PB member can open that day; Myles shifts
# to (14,23) when he's the only PB closer). Compensation shifts apply on manager off-days.
JAY_STD   = {0: (6, 15), 3: (10, 20), 4: (10, 20), 5: (10, 20), 6: (11, 17)}
JAY_OPEN  = {            3: (9, 19),  4: (9, 19),  5: (9, 19),  6: (9, 17)}
MYLES_STD = {0: (12, 21), 1: (11, 20), 2: (11, 20), 5: (11, 20), 6: (12, 21)}
MGR_OFFDAY_SHIFT = {
    ('Jay Martin', 1): (10.0, 20.0), ('Jay Martin', 2): (10.0, 20.0),
    ('Myles Palmer', 3): (11.0, 20.0), ('Myles Palmer', 4): (11.0, 20.0),
}


def early_ok(person, d):
    """Who may start before 9am on day d (mirrors the solver's gen() floor).
    Structural/weekly, so it lives here and is shared by solver2.py and test_protocol.py."""
    return (person in ('Jay Martin', 'Bowen Benedict')
            or (person in ('Gobi Weathers', 'Trinity Stringer') and d == 5)
            or (person == 'James Baker' and d == 6))


# ── Per-person special constraints (collected here so they're visible in one place) ──
LATEST_END = {'Molly Summers': 17}            # never scheduled to end after this hour
WEAK5_MAX_DAYS = {'Bryan Bishop': 1}          # overrides the default weak5 cap of 2 days/week
# Adam Van Bogaert works a fixed 1pm–11pm closing pattern:
MUST_CLOSE_AT = {'Adam Van Bogaert': 23.0}    # when working, the shift must END exactly here
EXTRA_SHIFTS  = {'Adam Van Bogaert': [(13.0, 23.0)]}  # seed shifts the anchor grid can't make
                                                       # (13:00 is a dead-zone start time)
# Adam is normally Mon-Fri only. If he requests a weekday off, he's available for his usual
# 1pm-11pm pattern on Sat and/or Sun instead (make-up shift, so he can still hit his hours) —
# only on a weekend day he hasn't ALSO requested off himself.
WEEKEND_MAKEUP = {'Adam Van Bogaert': (13.0, 23.0)}
# Per-person hard weekly shift-count caps, below the generic ≤5/week cap everyone else gets.
# Shared with test_protocol.py's reachability DP so it can't overstate someone's max achievable
# hours by assuming the generic 5-shift cap applies to them.
SHIFT_CAP = {'Jacob Cothern': 2, 'Reilly Weakley': 3}

# ── 12-hour close-then-open rest rule (one definition for the constraint, audit, and test) ──
REST_HOURS = 12   # required rest between a late close and the next day's opening shift
LATE_CLOSE = 21   # a shift ending at/AFTER this (9pm) is a "late close" that triggers the rule

def rest_floor(prev_close_end):
    """Earliest the NEXT day may start, given the previous day ended at prev_close_end.
    A close at/after LATE_CLOSE forces a start ≥ end − REST_HOURS; otherwise no restriction (0)."""
    return prev_close_end - REST_HOURS if prev_close_end >= LATE_CLOSE else 0.0

def rest_conflict(prev_close_end, next_start):
    """True if ending at prev_close_end then starting at next_start the next day breaks the rule."""
    return next_start < rest_floor(prev_close_end)
