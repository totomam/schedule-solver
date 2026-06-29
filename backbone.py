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

# Non-manager backbone: {(person, day): (start_h, end_h)} — fixed shifts for the week.
STATIC_BACKBONE = {
    **{('Bowen Benedict', d): (8, 16) for d in range(5)},
    ('Gobi Weathers', 0): (16, 23),
    ('Gobi Weathers', 1): (11, 17),   # Tue 11a (not 10a): 12h rule after Mon 11p close
    ('Gobi Weathers', 2): (9, 17),
    ('Gobi Weathers', 5): (9, 17),
    ('Gobi Weathers', 6): (15, 23),
    ('Mary Dean', 5): (15, 23),
    # James Baker requested off all 7 days this week (vacation) — no backbone.
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
