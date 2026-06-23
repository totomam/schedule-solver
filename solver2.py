import json, math, pulp, os
from collections import defaultdict
from datetime import datetime, timedelta
_OUT = os.environ.get('SCHED_OUT', 'schedule.json')   # tests set SCHED_OUT to write elsewhere
# Derive the "_active" path by stripping a trailing .json only, so the two outputs never collide
# (str.replace would hit every '.json' in the path and would no-op when there's no extension).
_base = _OUT[:-5] if _OUT.endswith('.json') else _OUT
_OUT_ACTIVE = _base + '_active.json'
_THREADS=int(os.environ.get('SCHED_THREADS','0'))  # >0 enables HiGHS parallel B&B
_HIGHS_SEED=int(os.environ.get('SCHED_HIGHS_SEED','-1'))  # -1 = HiGHS default
_AVAIL_FILE    = os.environ.get('SCHED_AVAIL',    'avail_6_29.json')
_REQOFF_FILE   = os.environ.get('SCHED_REQOFF',   'reqoff_6_29.json')
_FORECAST_FILE = os.environ.get('SCHED_FORECAST', 'forecast_6_29.json')
with open(_AVAIL_FILE)    as _f: av=json.load(_f)
with open(_REQOFF_FILE)   as _f: req=json.load(_f)
with open(_FORECAST_FILE) as _f: fc=json.load(_f)
allowed=fc['allowed_hours']
dn=['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
PB={'John Martin (Jay)','Myles Palmer','Bowen Benedict','James Baker','Trinity Stringer','Gobi Weathers','Mary Dean'}
# NO_BREAK = people who do NOT clock out for an unpaid break (no 0.5h deduction).
# As of now: only the two managers (Jay/Myles) get paid = raw hours (no break deduction).
NO_BREAK={'John Martin (Jay)','Myles Palmer'}
def paid_val(n,a,b):
    r=b-a; return r if n in NO_BREAK else (r-0.5 if r>=5 else r)
TEN_HR=PB|{'Adam Van Bogaert','Mason Doyle','Michael Calderon','Molly Summers','Noah Hiner','Ava Shade','Remi Sullinger','Izzy Simpson','Zac Duffy','Kara Thompson'}
weak3={'Brian Carver','Bryan Bishop','Jason Britt'}
weak5=weak3|{'Emily Owens'}
prep={'Michael Calderon','Tiffany Huffman','Noah Hiner','Gracelyn Dailey','Molly Summers','Reilly Weakley'}
FT_nonleader={'Adam Van Bogaert','Mason Doyle','Michael Calderon','Molly Summers','Noah Hiner','Ava Shade','Izzy Simpson','Remi Sullinger','Reilly Weakley'}
strong_PT={'Gracelyn Dailey','Cai Cotton','Sandya Wright','Kara Thompson','Nathan Paaswee','Peyton Shaw','Reese Bezehertny'}
regular_PT={'Tiffany Huffman','Amiyah Bartley','Harper Flynn','Jonathan Beacham',
            'Hayden Roush','Logan Frias','Shayden Howard','John Dugan',
            'Kayden Anderson','Richard Raglin','Ryder','Oliver Croasdaile'}

def avwin(n,d):
    w=av[n][d]
    if w=='X' or n in req[dn[d]]: return None
    if w in('any','open'): return [6,23]
    return w
def avail_days(n): return [d for d in range(7) if avwin(n,d)]

fixed={}
def fx(n,d,a,b): fixed[(n,d)]=[a,b]
# ===== BACKBONE — update each week =====
for d in range(5): fx('Bowen Benedict',d,8,16)
# Jay standard: Mon 6a-3p, Thu/Fri/Sat 10a-8p, Sun 11a-5p. Off Tue/Wed.
# Deviate only when one manager must cover for the other's absence, or backstop open/close needed.
fx('John Martin (Jay)',0,6,15); fx('John Martin (Jay)',1,10,20); fx('John Martin (Jay)',2,10,20)
fx('John Martin (Jay)',3,10,20); fx('John Martin (Jay)',4,10,20)
fx('John Martin (Jay)',5,10,20); fx('John Martin (Jay)',6,11,17)
# Myles standard: 11a-8p all backbone days. Off Thu/Fri.
fx('Myles Palmer',0,11,20); fx('Myles Palmer',1,11,20); fx('Myles Palmer',2,11,20)
fx('Myles Palmer',5,11,20); fx('Myles Palmer',6,11,20)
fx('Gobi Weathers',0,16,23); fx('Gobi Weathers',1,11,17); fx('Gobi Weathers',2,9,17); fx('Gobi Weathers',5,8,16); fx('Gobi Weathers',6,15,23)
fx('Mary Dean',5,15,23)
fx('James Baker',2,15,23); fx('James Baker',6,8,16)
fx('Tiffany Huffman',0,9,16)
fx('Trinity Stringer',4,17,23)

# Shift anchors: three real-world windows (9am-noon, 2pm-6pm, 8pm-11pm).
# Noon-2pm (12:15-1:45) and 6pm-8pm (6:15-7:45) are dead zones — no starts or ends in between.
# Boundaries (12:00, 14:00, 18:00, 20:00) are valid start/end times.
ANCH_START = ([round(9  +0.25*i,2) for i in range(int((12-9 )/0.25)+1)]  # 9:00-12:00 (13 values)
            + [round(14 +0.25*i,2) for i in range(int((18-14)/0.25)+1)]) # 14:00-18:00 (17 values)
ANCH_END   = ([round(14 +0.25*i,2) for i in range(int((18-14)/0.25)+1)]  # 14:00-18:00 (17 values)
            + [round(20 +0.25*i,2) for i in range(int((23-20)/0.25)+1)]) # 20:00-23:00 (13 values)
def gen(n,d):
    w=avwin(n,d)
    if not w: return []
    lo,hi=w; out=[]; maxlen=10 if n in TEN_HR else 8
    # Only certain leaders/managers may start before 9am on their designated days.
    # All others (and leaders on non-designated days) are floored at 9am.
    if n not in PB: lo=max(lo,9)
    elif n not in ('John Martin (Jay)','Bowen Benedict'):
        if not ((n in ('Gobi Weathers','Trinity Stringer') and d==5) or (n=='James Baker' and d==6)):
            lo=max(lo,9)
    # Molly never works past 5pm
    if n=='Molly Summers': hi=min(hi,17)
    # Adam's 10h standard shift: 1pm-11pm. 13:00 is in the ANCH dead zone so add it explicitly.
    if n=='Adam Van Bogaert' and lo<=13.0 and hi>=23.0:
        out.append((13.0, 23.0))
    for a in ANCH_START:
        if a<lo or a>hi-4: continue
        for b in ANCH_END:
            if b<=a or b>hi: continue
            L=b-a
            # Forbidden end times: dead zone 6pm-8pm (18:15-19:45), plus 8:15pm and 8:45pm
            # (evening departures land only at 8:00, 8:30, or 9:00+). 6:00pm & 8:00pm ok.
            # Also no one may end before 2pm (before 3pm on Sunday) — hard rule, no exceptions.
            if L<4 or L>maxlen or (18 < b < 20) or b in (20.25, 20.75): continue
            # Adam always ends at 11pm (set pattern)
            if n=='Adam Van Bogaert' and b!=23.0: continue
            # All PB (shift leaders AND managers): if closing (end ≥10pm), must end at exactly 11pm
            if n in PB and b>=22 and b!=23.0: continue
            min_end = 15 if d==6 else 14   # Sunday: nobody leaves before 3pm; else 2pm
            if b<min_end: continue
            out.append((round(a,2),round(b,2)))
    return out

prob=pulp.LpProblem('sched',pulp.LpMinimize)
shifts={}; x={}
people=list(av)
pidx={n:i for i,n in enumerate(people)}  # OPT: O(1) index lookup
# OPT: dedup candidate shifts by coverage signature (rule-preserving).
# Two shifts that cross the identical set of all constraint thresholds AND have identical
# paid/raw hours are interchangeable; keep one representative. Preserves exact close-ends and
# early starts so the 12-hour close-then-open rule is unaffected.
_TH=[9,10,12,14,15,15.5,16,16.5,17,21,21.5,22,22.5]
def _sig(a,b,n):
    s=[a<=t<b for t in _TH]
    s+=[a<=9,a<=10,a<=12,round(a,2)==17.5,round(a,2)==18,round(b,2) in (14,14.5),
        b>=22,b>=22.5,b>21,b>21.5,b>17]
    s.append(round(paid_val(n,a,b)*4)); s.append(round((b-a)*4))
    s.append(round(b,2) if b>=21 else 0)        # exact close-end (12hr rule)
    s.append(round(a,2) if a<=11.25 else 0)     # exact early start (12hr rule)
    return tuple(s)
def dedup(cands,n):
    seen={}; 
    for (a,b) in cands:
        k=_sig(a,b,n)
        if k not in seen: seen[k]=(a,b)
    return list(seen.values())
for n in people:
    for d in range(7):
        shifts[(n,d)]=[tuple(fixed[(n,d)])] if ((n,d) in fixed and avwin(n,d) is not None) else dedup(gen(n,d),n)
        for i in range(len(shifts[(n,d)])):
            x[(n,d,i)]=pulp.LpVariable(f'x_{pidx[n]}_{d}_{i}',cat='Binary')
for (n,d) in fixed:
    if (n,d,0) in x: prob += x[(n,d,0)]==1
for n in people:
    for d in range(7):
        if shifts[(n,d)]: prob += pulp.lpSum(x[(n,d,i)] for i in range(len(shifts[(n,d)])))<=1

# OPT: flatten the per-day (person, shift-index, start, end) tuples ONCE so the hot constraint
# helpers don't rebuild the people x shifts cross product on every call.
SD={d:[(n,i,a,b,paid_val(n,a,b)) for n in people for i,(a,b) in enumerate(shifts[(n,d)])] for d in range(7)}
_trio={'Gobi Weathers','James Baker','Trinity Stringer'}
_no_early={'John Martin (Jay)','Bowen Benedict'}
# OPT: pre-filter SD[d] into named variable lists once; the constraint loop then calls lpSum on a
# short pre-filtered list instead of scanning all SD[d] entries with a lambda predicate each time.
_SDF={}
for d in range(7):
    sd=SD[d]
    _SDF[d,'h14']   =[x[(n,d,i)] for (n,i,a,b,pv) in sd if a<=14<b]
    _SDF[d,'h15']   =[x[(n,d,i)] for (n,i,a,b,pv) in sd if a<=15<b]
    _SDF[d,'h155']  =[x[(n,d,i)] for (n,i,a,b,pv) in sd if a<=15.5<b]
    _SDF[d,'h16']   =[x[(n,d,i)] for (n,i,a,b,pv) in sd if a<=16<b]
    _SDF[d,'h165']  =[x[(n,d,i)] for (n,i,a,b,pv) in sd if a<=16.5<b]
    _SDF[d,'opener']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if n!='John Martin (Jay)' and a<=10]
    _SDF[d,'lunch'] =[x[(n,d,i)] for (n,i,a,b,pv) in sd if a<=12<b]
    _SDF[d,'dinner']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if b>17]
    _SDF[d,'cl225'] =[x[(n,d,i)] for (n,i,a,b,pv) in sd if b>=22.5]
    _SDF[d,'cl21']  =[x[(n,d,i)] for (n,i,a,b,pv) in sd if b>21]
    _SDF[d,'cl215'] =[x[(n,d,i)] for (n,i,a,b,pv) in sd if b>21.5]
    _SDF[d,'pb_op'] =[x[(n,d,i)] for (n,i,a,b,pv) in sd if n in PB and n!='John Martin (Jay)' and a<=9]
    _SDF[d,'pb_cl'] =[x[(n,d,i)] for (n,i,a,b,pv) in sd if n in PB and b>=22]
    _SDF[d,'w3_ln'] =[x[(n,d,i)] for (n,i,a,b,pv) in sd if n in weak3 and a<=12<b]
    _SDF[d,'w3_dn'] =[x[(n,d,i)] for (n,i,a,b,pv) in sd if n in weak3 and b>17]
    _SDF[d,'la1725']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if a==17.25]
    _SDF[d,'la175'] =[x[(n,d,i)] for (n,i,a,b,pv) in sd if a==17.5]
    _SDF[d,'la1775']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if a==17.75]
    _SDF[d,'la18']  =[x[(n,d,i)] for (n,i,a,b,pv) in sd if a==18.0]
    _SDF[d,'dep20'] =[x[(n,d,i)] for (n,i,a,b,pv) in sd if b==20.0 and n not in PB]
    _SDF[d,'dep205']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if b==20.5 and n not in PB]
    _SDF[d,'dep14'] =[x[(n,d,i)] for (n,i,a,b,pv) in sd if b in (14,14.5)]
    _SDF[d,'trio_cl']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if n in _trio and b>=22]
    _SDF[d,'e2225'] =[x[(n,d,i)] for (n,i,a,b,pv) in sd if b==22.25]
    _SDF[d,'e225']  =[x[(n,d,i)] for (n,i,a,b,pv) in sd if b==22.5]
    _SDF[d,'e2275'] =[x[(n,d,i)] for (n,i,a,b,pv) in sd if b==22.75]
    _SDF[d,'e23']   =[x[(n,d,i)] for (n,i,a,b,pv) in sd if b==23.0]
    _SDF[d,'stag9'] =[x[(n,d,i)] for (n,i,a,b,pv) in sd if n not in _no_early and a<=9]
    _SDF[d,'prep9'] =[x[(n,d,i)] for (n,i,a,b,pv) in sd if n in prep and a<=9]

twoTar=[8,8,8,8,8,9,11]; threeTar=[6,6,6,6,7,8,8]; fourTar=[5,5,5,5,6,7,6]
Otar=[6,6,6,6,6,6,6]; Ltar=[9,9,9,9,10,10,11]; Dtar=[10,10,10,11,14,13,12]; Ctar=[5,5,5,5,6,6,6]

# Soft-constraint helpers: convert tight equality/ceiling constraints to penalised slack variables.
# Penalty _CPEN=500 >> max possible objective gain (~80 units) so slacks are zero in any optimal
# solution — the final schedule is identical, but the feasible region is much larger, letting
# HiGHS find the first integer-feasible point dramatically faster.
_CPEN=500
_cov_slk=[]
def _sc(e,cap,t):   # soft ceiling: e <= cap + slack
    global prob; _s=pulp.LpVariable(t,lowBound=0); prob+=e<=cap+_s; _cov_slk.append(_s)
def _sf(e,fl,t):    # soft floor: e + slack >= fl
    global prob; _s=pulp.LpVariable(t,lowBound=0); prob+=e+_s>=fl; _cov_slk.append(_s)
# Hours floor soft constraints — activated only when req-offs make the target unreachable.
# _HPEN < _CPEN so coverage always wins, but hours targets are still strongly preferred.
_HPEN=495
_hrs_slk=[]
def _sh(expr,floor,tag):
    global prob; _s=pulp.LpVariable(f'hs_{tag}',lowBound=0); prob+=expr+_s>=floor; _hrs_slk.append((tag,floor,_s))

for d in range(7):
    _h14=pulp.lpSum(_SDF[d,'h14']); _h15=pulp.lpSum(_SDF[d,'h15']); _h16=pulp.lpSum(_SDF[d,'h16'])
    _cl225=pulp.lpSum(_SDF[d,'cl225']); _cl21=pulp.lpSum(_SDF[d,'cl21'])
    _op=pulp.lpSum(_SDF[d,'opener'])
    # All coverage floors are soft — _CPEN=500 makes slack always 0 in normal solutions;
    # soft floors prevent infeasibility when extreme req-offs deplete a day.
    _sf(_h14,twoTar[d],                         f'sh14f_{d}')
    _sf(_h15,threeTar[d],                        f'sh15f_{d}')
    _sf(_h16,fourTar[d],                         f'sh16f_{d}')
    _sf(_cl225,Ctar[d]-1,                        f'scl225fh_{d}')
    _sf(_op,Otar[d],                             f'sopf_{d}')
    _sf(pulp.lpSum(_SDF[d,'lunch']),Ltar[d],     f'slnf_{d}')
    _sf(pulp.lpSum(_SDF[d,'dinner']),Dtar[d],    f'sdnf_{d}')
    _sf(pulp.lpSum(_SDF[d,'cl215']),(7 if d>=4 else 6), f'scl215f_{d}')
    _sf(pulp.lpSum(_SDF[d,'pb_op']),1,           f'spbop_{d}')
    _sf(pulp.lpSum(_SDF[d,'pb_cl']),1,           f'spbcl_{d}')
    _sf(pulp.lpSum(_SDF[d,'prep9']),1,           f'sprep9_{d}')
    _sf(_cl21,(8 if d in (4,5) else 7),          f'scl21f_{d}')
    # Soft ceilings/targets — penalised, not hard. Ceiling == exact target → soft equality.
    _sc(_h14,twoTar[d],         f'sh14_{d}')
    _sc(_h15,threeTar[d],       f'sh15_{d}')
    _sc(_h16,fourTar[d],        f'sh16_{d}')
    _sf(_cl225,Ctar[d],         f'scl225f_{d}')
    _sc(_cl225,Ctar[d],         f'scl225c_{d}')
    _sc(_op,Otar[d],            f'sop_{d}')
    if d in (4,5): _sc(_cl21,8,f'scl21_{d}')
    _sc(pulp.lpSum(_SDF[d,'h155']),9,   f'sh155_{d}')
    _sc(pulp.lpSum(_SDF[d,'h165']),8,   f'sh165_{d}')
    _cap_8=1 if d in (4,5) else 2
    if _SDF[d,'dep20']:   _sc(pulp.lpSum(_SDF[d,'dep20']),  _cap_8, f'sdep20_{d}')
    if _SDF[d,'dep205']:  _sc(pulp.lpSum(_SDF[d,'dep205']), 2,      f'sdep205_{d}')
    if _SDF[d,'dep14']:   _sc(pulp.lpSum(_SDF[d,'dep14']),  2,      f'sdep14_{d}')
    if _SDF[d,'trio_cl']: _sc(pulp.lpSum(_SDF[d,'trio_cl']),1,      f'strio_{d}')
    # Closer end-time staggering: 2x11pm, 2x10:30pm, 1x10:15pm, 1x10:45pm
    # e23 ceiling is 3 (not 2): shift leaders forced to 23.0 can fill 2 slots,
    # so a manager who also closes would push ceiling of 2 over. Allow 3.
    # e2225 (10:15pm): ceiling only — adding a floor requires a 7th closer slot since
    # 22.25 < 22.5 doesn't count in cl225, which creates unavoidable budget conflicts.
    for _key,_floor,_ceil in (('e23',2,3),('e225',2,2),('e2275',1,1)):
        if _SDF[d,_key]:
            _e=pulp.lpSum(_SDF[d,_key])
            _sf(_e,_floor,f's{_key}f_{d}')
            _sc(_e,_ceil, f's{_key}c_{d}')
    if _SDF[d,'e2225']:
        _sc(pulp.lpSum(_SDF[d,'e2225']),1,f'se2225c_{d}')
    if _SDF[d,'stag9']:   _sc(pulp.lpSum(_SDF[d,'stag9']),  2,      f'sstag9_{d}')
    for _key in ('la1725','la175','la1775','la18'):
        if _SDF[d,_key]: _sc(pulp.lpSum(_SDF[d,_key]),1,   f's{_key}_{d}')
    if _SDF[d,'w3_ln']: _sc(pulp.lpSum(_SDF[d,'w3_ln']),1, f'sw3ln_{d}')
    if _SDF[d,'w3_dn']: _sc(pulp.lpSum(_SDF[d,'w3_dn']),1, f'sw3dn_{d}')

for n in people:
    if n=='John Martin (Jay)': continue
    prob += pulp.lpSum(x[(n,d,i)] for d in range(7) for i in range(len(shifts[(n,d)])))<=5
def hours_expr(n): return pulp.lpSum(x[(n,d,i)]*(b-a) for d in range(7) for i,(a,b) in enumerate(shifts[(n,d)]))
_sh(hours_expr('Trinity Stringer'),39,'Trinity_Stringer')
_sh(hours_expr('Gobi Weathers'),37,'Gobi_Weathers')
for n in FT_nonleader:
    if n == 'Adam Van Bogaert':
        prob += hours_expr(n)<=40
        if len(avail_days(n)) >= 4:
            prob += hours_expr(n) >= 40
        else:
            _sh(hours_expr(n), 40, 'Adam_Van_Bogaert')
        continue
    prob += hours_expr(n)<=40
    floor = 33
    max_per_day = 10.0 if n in TEN_HR else 8.0
    min_days = math.ceil(floor / max_per_day)
    if len(avail_days(n)) >= min_days:
        _sh(hours_expr(n),floor,n.replace(' ','_'))
prob += hours_expr('Zac Duffy')<=35; _sh(hours_expr('Zac Duffy'),30,'Zac_Duffy')
for n in regular_PT:
    _sh(hours_expr(n),12,n.replace(' ','_'))
for n in people:
    if n in ('John Martin (Jay)','Myles Palmer'): continue  # managers: no 40h cap
    prob += hours_expr(n)<=40
prob += hours_expr('Myles Palmer') >= 45  # hard — solver works off-days to compensate if req'd off
prob += hours_expr('Myles Palmer')<=52
prob += hours_expr('John Martin (Jay)') >= 45  # hard — solver works off-days to compensate if req'd off
prob += hours_expr('John Martin (Jay)')<=54
_sh(hours_expr('James Baker'),39,'James_Baker')
_sh(hours_expr('Mary Dean'),39,'Mary_Dean')
prob += hours_expr('Gracelyn Dailey')<=30
for n in strong_PT:
    _sh(hours_expr(n),20,n.replace(' ','_'))
for n in weak5:
    _sh(hours_expr(n),4,n.replace(' ','_'))
# weak5: prefer 1 day each. Hard cap 2 days; Bryan capped at 1.
for n in weak5:
    prob += pulp.lpSum(x[(n,d,i)] for d in range(7) for i in range(len(shifts[(n,d)])))<=2
prob += pulp.lpSum(x[('Bryan Bishop',d,i)] for d in range(7) for i in range(len(shifts[('Bryan Bishop',d)])))<=1

# Per-person above-floor incentive: small penalty for hours exceeding individual floor.
# Nudges the solver to stay near each floor without a hard ceiling — if coverage or another
# person's floor demands the extra hours, the penalty yields (it's << _HPEN).
_AFLOOR_PEN = 5
_afloor_terms = []
_floor_map = ([(n,33) for n in FT_nonleader if n!='Adam Van Bogaert']
            + [(n,20) for n in strong_PT]
            + [(n,12) for n in regular_PT]
            + [(n, 4) for n in weak5]
            + [('Zac Duffy',30),('Trinity Stringer',39),('Gobi Weathers',37),
               ('James Baker',39),('Mary Dean',39),
               ('Myles Palmer',45),('John Martin (Jay)',45)])
for _n, _fl in _floor_map:
    _ov = pulp.LpVariable(f'ovf_{pidx[_n]}', lowBound=0)
    prob += _ov >= hours_expr(_n) - _fl
    _afloor_terms.append(_ov)

# CHANGE 4: 12-hour close-then-open rule — AGGREGATED formulation.
# A day-d close ending at b1 conflicts with a day-(d+1) shift starting at a2 when (24-b1)+a2 < 12,
# i.e. a2 < b1 - 12. Since each person works <=1 shift/day, we don't need a constraint per pair.
# For each distinct close-end time b1 on day d, all next-day shifts starting before (b1-12) are
# mutually exclusive with the close. One constraint per (person, day, distinct-close-end):
#   x[close@b1] + sum(x[next-day shifts starting < b1-12]) <= 1
for n in people:
    for d in range(6):
        nxt = shifts[(n,d+1)]
        if not nxt: continue
        # group day-d shifts by close-end time (only closes b1>=21 can ever conflict)
        by_end = defaultdict(list)
        for i,(a1,b1) in enumerate(shifts[(n,d)]):
            if b1 >= 21: by_end[b1].append(i)
        for b1, idxs in by_end.items():
            thresh = b1 - 12  # next-day starts strictly below this conflict
            early = [j for j,(a2,b2) in enumerate(nxt) if a2 < thresh]
            if not early: continue
            # all of (these closes) + (these early next-day shifts) can host at most ONE selection,
            # because picking any close forbids any conflicting early open and vice-versa.
            prob += (pulp.lpSum(x[(n,d,i)] for i in idxs)
                     + pulp.lpSum(x[(n,d+1,j)] for j in early)) <= 1

# ===== Both managers off → force all available shift leaders to work that day =====
# When Jay and Myles are both unavailable on a day (req'd off or avail="X"), every
# shift leader who IS available must work to guarantee PB open/close coverage.
_PB_LEADERS = [n for n in PB if n not in NO_BREAK]  # Bowen, James, Trinity, Gobi, Mary
for d in range(7):
    if avwin('John Martin (Jay)',d) is None and avwin('Myles Palmer',d) is None:
        for _n in _PB_LEADERS:
            _day_shifts = shifts.get((_n,d),[])
            if _day_shifts:
                prob += pulp.lpSum(x[(_n,d,i)] for i in range(len(_day_shifts))) >= 1

# ===== NO ZERO-SHIFT for anyone available (>=1 day avail must get >=1 shift) =====
# Make it a HARD constraint for everyone with availability, EXCEPT allow the solver to drop
# someone only if infeasible. Use soft with big penalty to stay feasible.
zero_pen=[]
for n in people:
    if n in ('John Martin (Jay)','Myles Palmer'): continue  # managers handled by fixed
    ad=avail_days(n)
    if not ad: continue
    total_shifts=pulp.lpSum(x[(n,d,i)] for d in range(7) for i in range(len(shifts[(n,d)])))
    z=pulp.LpVariable(f'zero_{pidx[n]}',cat='Binary')  # 1 if person gets ZERO shifts
    # total_shifts >= 1 - z  (if z=0, must have >=1)
    prob += total_shifts >= 1 - z
    zero_pen.append(z)

# Objective: land total paid hours in [allowed+25, allowed+30], minimize zero-shift people,
# minimize weak5 usage, prefer short shifts. No exact target — any value in the window is fine.
# SD already carries pv=paid_val(n,a,b) — use it directly everywhere paid hours are needed.
total_paid=pulp.lpSum(x[(n,d,i)]*pv for d in range(7) for (n,i,a,b,pv) in SD[d])
# Per-day labor balance: keep each day's paid hours within a reasonable band of its allowed,
# so the weekly variance doesn't pile onto one day / starve another.
for d in range(7):
    day_paid=pulp.lpSum(x[(n,d,i)]*pv for (n,i,a,b,pv) in SD[d])
    prob += day_paid >= allowed[d]-3      # no day more than 3h under its allowed budget
    prob += day_paid <= allowed[d]+14     # and not wildly over

# Weekly paid hours must land in [allowed+25, allowed+30] — hard range, no penalty term.
prob += total_paid >= sum(allowed)+25
prob += total_paid <= sum(allowed)+30
weak_use=pulp.lpSum(x[(n,d,i)] for d in range(7) for (n,i,a,b,pv) in SD[d] if n in weak5)
# Preference: favor short 4-4.5h shifts (no break) over 5-5.5h shifts (which lose 0.5h to break).
# Same labor, more days, no break to manage. Light penalty on 5-5.5h shifts for non-managers.
short_pref=pulp.lpSum(x[(n,d,i)] for d in range(7) for (n,i,a,b,pv) in SD[d]
                      if n not in NO_BREAK and 5<=(b-a)<=5.5)
# Soft default-schedule preference for managers: discourage Jay from working Tue/Wed and
# Myles from working Thu/Fri (their standard off-days). High enough to keep standard schedule;
# low enough to allow backstop coverage when no other PB opener/closer is available.
_JAY_OFFDAYS  = {1,2}   # Tue, Wed
_MYLES_OFFDAYS = {3,4}  # Thu, Fri
mgr_offday = (pulp.lpSum(x[('John Martin (Jay)',d,i)]  for d in _JAY_OFFDAYS   for i in range(len(shifts[('John Martin (Jay)',d)])))
            + pulp.lpSum(x[('Myles Palmer',d,i)]       for d in _MYLES_OFFDAYS  for i in range(len(shifts[('Myles Palmer',d)]))))
# Manager role priorities: Jay is the backstop OPENER, Myles is the backstop CLOSER.
# Penalise Jay for taking closing shifts (b=23) and Myles for taking opening shifts (a<=10).
# Penalty 20 < mgr_offday 30 < coverage floor 500, so backstop still fires when needed
# but the preferred manager is chosen first.
jay_closes  = pulp.lpSum(x[('John Martin (Jay)',d,i)]
                          for d in range(7)
                          for i,(a,b) in enumerate(shifts[('John Martin (Jay)',d)])
                          if b == 23.0)
myles_opens = pulp.lpSum(x[('Myles Palmer',d,i)]
                          for d in range(7)
                          for i,(a,b) in enumerate(shifts[('Myles Palmer',d)])
                          if a <= 10)
prob += (5000*pulp.lpSum(zero_pen) + 8*weak_use + 0.3*short_pref + 30*mgr_offday
         + 20*jay_closes + 20*myles_opens
         + _CPEN*pulp.lpSum(_cov_slk) + _HPEN*pulp.lpSum(s for _,_,s in _hrs_slk)
         + _AFLOOR_PEN*pulp.lpSum(_afloor_terms))

print(f"Vars: {len(x)}. Solving with HiGHS...")
_tl=int(os.environ.get('SCHED_TIMELIMIT','240'))
_gr=float(os.environ.get('SCHED_GAPREL','0.25'))
_kw=dict(msg=False,timeLimit=_tl,gapRel=_gr)
if _THREADS: _kw['threads']=_THREADS
else: _kw['threads']=4
if _HIGHS_SEED >= 0: _kw['randomSeed']=_HIGHS_SEED
prob.solve(pulp.HiGHS(**_kw))
_var=round(pulp.value(total_paid)-sum(allowed),2) if pulp.value(total_paid) else '?'
print("Status:",pulp.LpStatus[prob.status],"| paid",pulp.value(total_paid),"| var",_var,"| zeros",sum(1 for z in zero_pen if z.value() and z.value()>0.5))
_viol=[v.name for v in _cov_slk if v.value() and v.value()>0.001]
if _viol: print(f"WARNING: {len(_viol)} coverage slack(s) nonzero: {_viol[:5]}...")
sol={n:[None]*7 for n in people}
for d in range(7):
    for (n,i,a,b,pv) in SD[d]:
        v=x[(n,d,i)].value()
        if v and v>0.5: sol[n][d]=[a,b]
with open(_OUT,'w') as _f: json.dump(sol,_f)
with open(_OUT_ACTIVE,'w') as _f: json.dump({n:sh for n,sh in sol.items() if any(sh)},_f)

# ---- Compact status summary ----
def _pd(sh,n):
    if not sh: return 0
    r=sh[1]-sh[0]; return r if n in NO_BREAK else (r-0.5 if r>=5 else r)
def _hd(d,t): return sum(1 for n in sol if sol[n][d] and sol[n][d][0]<=t<sol[n][d][1])
def _O(d): return sum(1 for n in sol if n!='John Martin (Jay)' and sol[n][d] and sol[n][d][0]<=10)
def _C(d): return sum(1 for n in sol if sol[n][d] and sol[n][d][1]>=22.5)
# ★ = over target (excess labor/coverage); ! = under target (shortage); blank = on target
def _ck(v,t,exact=True):
    if v>t: return '★'
    if v<t: return '!'
    return ' '
def _ckf(v,t): return '!' if v<t else ' '  # floor only: flag if under

print(f"Day  Var    O   L    D   C  9p 930  2pm  3pm  4pm")
for d in range(7):
    var=sum(_pd(sol[n][d],n) for n in sol)-allowed[d]
    L=sum(1 for n in sol if sol[n][d] and sol[n][d][0]<=12<sol[n][d][1])
    D=sum(1 for n in sol if sol[n][d] and sol[n][d][1]>17)
    O=_O(d); C=_C(d); h14=_hd(d,14); h15=_hd(d,15); h16=_hd(d,16)
    cl21=_hd(d,21); cl215=_hd(d,21.5)
    print(f"{dn[d]:3}{var:+6.1f}  "
          f"{O}{_ck(O,Otar[d])}"
          f"{L:3}{_ckf(L,Ltar[d])}"
          f"{D:4}{_ckf(D,Dtar[d])}"
          f"{C:3}{_ck(C,Ctar[d])}"
          f"  {cl21:2}/{cl215:2}"
          f"  {h14}{_ck(h14,twoTar[d])}"
          f"{h15:3}{_ck(h15,threeTar[d])}"
          f"{h16:3}{_ck(h16,fourTar[d])}")
tot=sum(_pd(sol[n][d],n) for n in sol for d in range(7))-sum(allowed)
print(f"TOTAL var: {tot:+.1f} | Status {pulp.LpStatus[prob.status]}")

# ---- Inline rules audit ----
_fails=[]
# 12h close-then-open
for n in people:
    for d in range(6):
        s0=sol[n][d]; s1=sol[n][d+1]
        if s0 and s1 and s0[1]>21 and s1[0]<s0[1]-12:
            _fails.append(f"12h: {n} {dn[d]}end={s0[1]} {dn[d+1]}start={s1[0]}")
# Leader open and close each day
for d in range(7):
    if not any(sol[n][d] and sol[n][d][0]<=9 for n in PB if n!='John Martin (Jay)'):
        _fails.append(f"LeaderOpen: {dn[d]} no leader/manager opens")
    if not any(sol[n][d] and sol[n][d][1]>=22 for n in PB):
        _fails.append(f"LeaderClose: {dn[d]} no leader/manager closes")
# Trio at most 1 close per day
for d in range(7):
    tc=sum(1 for n in _trio if sol[n][d] and sol[n][d][1]>=22)
    if tc>1: _fails.append(f"TrioClose: {dn[d]} {tc} of Gobi/James/Trinity closing")
# Overtime check — all hours-under is reported via HoursUnder (_hrs_slk) below
for n in people:
    raw=sum(sol[n][d][1]-sol[n][d][0] for d in range(7) if sol[n][d])
    if n not in ('John Martin (Jay)','Myles Palmer') and raw>40.01:
        _fails.append(f"OT: {n} {raw:.1f}h")
# No starts before 9am except authorised people
_pre9_ok={'John Martin (Jay)','Bowen Benedict'}
for n in people:
    for d in range(7):
        sh=sol[n][d]
        if not sh: continue
        ok = n in _pre9_ok or (n in ('Gobi Weathers','Trinity Stringer') and d==5) or (n=='James Baker' and d==6)
        if sh[0]<9 and not ok:
            _fails.append(f"EarlyStart: {n} {dn[d]} {sh[0]}")
# No one ends before 2pm (3pm Sunday)
for n in people:
    for d in range(7):
        sh=sol[n][d]
        if sh and sh[1]<(15 if d==6 else 14):
            _fails.append(f"EarlyEnd: {n} {dn[d]} end={sh[1]}")
# Molly never past 5pm
for d in range(7):
    sh=sol.get('Molly Summers',[None]*7)[d]
    if sh and sh[1]>17: _fails.append(f"MollyLate: {dn[d]} end={sh[1]}")
# Coverage slacks (soft constraints violated)
_sviol=[v.name for v in _cov_slk if v.value() and v.value()>0.001]
if _sviol: _fails.append(f"CovSlack({len(_sviol)}): {_sviol[:4]}{'...' if len(_sviol)>4 else ''}")
# Hours floor slacks (person couldn't reach their hours target due to req-offs)
for _nm,_fl,_sv in _hrs_slk:
    if _sv.value() and _sv.value()>0.01:
        _fails.append(f"HoursUnder: {_nm.replace('_',' ')} {_fl-_sv.value():.1f}h actual (target ≥{_fl}h)")

print(f"Audit: {'PASS' if not _fails else str(len(_fails))+' issue(s):'}")
for _f in _fails: print(f"  {_f}")

# ---- Excel output ----
def _hfmt(h):
    hi=int(h); mi=round((h-hi)*60)
    if mi==60: hi+=1; mi=0
    if hi<12:   return f'{hi:02d}:{mi:02d}a'
    elif hi==12: return f'12:{mi:02d}p'
    else:        return f'{hi-12:02d}:{mi:02d}p'

def _write_xlsx(out_xlsx):
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        print("openpyxl not installed — skipping Excel output (pip install openpyxl)"); return

    GRAY = PatternFill('solid', fgColor='404040')
    WB10 = Font(color='FFFFFF', bold=True, size=10)
    WB9  = Font(color='FFFFFF', bold=True, size=9)
    P10  = Font(size=10)
    BD10 = Font(size=10, bold=True)
    CTR  = Alignment(horizontal='center')

    wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'Schedule'

    # Week start date for column headers
    ws_date = fc.get('week_start')
    if ws_date:
        dt0 = datetime.strptime(ws_date, '%Y-%m-%d')
        day_labels = [f'{dn[i]} {(dt0+timedelta(days=i)).strftime("%m/%d")}' for i in range(7)]
    else:
        day_labels = list(dn)

    # Column layout: A=name, B-D=Mon, E-G=Tue, ... T-V=Sun, W=Total
    def _dc(d): return 2+d*3, 3+d*3, 4+d*3  # (TimeIn, TimeOut, Hours) cols for day d
    hrs_cols = [4+d*3 for d in range(7)]      # D, G, J, M, P, S, V

    # Column widths
    ws.column_dimensions['A'].width = 22
    ws.column_dimensions['W'].width = 9
    for d in range(7):
        ci, co, ch = _dc(d)
        ws.column_dimensions[get_column_letter(ci)].width = 7
        ws.column_dimensions[get_column_letter(co)].width = 7
        ws.column_dimensions[get_column_letter(ch)].width = 6

    # Row 1 — day headers (merged)
    def _hdr(r, c, v, fnt, fill=GRAY, aln=None):
        cell = ws.cell(r, c, v); cell.font = fnt; cell.fill = fill
        if aln: cell.alignment = aln

    _hdr(1, 1, 'Employee Name', WB10)
    _hdr(1, 23, 'Total Hours', WB10, aln=CTR)
    for d in range(7):
        ci, _, ch = _dc(d)
        ws.merge_cells(start_row=1, start_column=ci, end_row=1, end_column=ch)
        _hdr(1, ci, day_labels[d], WB10, aln=CTR)

    # Row 2 — sub-headers
    for d in range(7):
        ci, co, ch = _dc(d)
        for col, label in [(ci,'Time In'),(co,'Time Out'),(ch,'Hours')]:
            _hdr(2, col, label, WB9, aln=CTR)

    # Employee rows (sorted alphabetically)
    sorted_ppl = sorted(sol.keys())
    for idx, n in enumerate(sorted_ppl):
        r = idx + 3
        ws.cell(r, 1, n).font = P10
        for d in range(7):
            ci, co, ch = _dc(d)
            sh = sol[n][d]
            if sh:
                ws.cell(r, ci, _hfmt(sh[0])).font = P10
                ws.cell(r, co, _hfmt(sh[1])).font = P10
                ws.cell(r, ch, round(sh[1]-sh[0], 4)).font = P10
            else:
                ws.cell(r, ci, 'X').font = P10
                ws.cell(r, co, 'X').font = P10
                ws.cell(r, ch, 0).font = P10
        hrs_formula = '+'.join(f'{get_column_letter(c)}{r}' for c in hrs_cols)
        ws.cell(r, 23, f'={hrs_formula}').font = P10

    last_emp = 2 + len(sorted_ppl)
    sr = last_emp + 2  # blank row then summary

    # Schedule Summary section
    ws.cell(sr, 1, 'Schedule Summary').font = BD10
    sr += 1

    summary_fields = [
        ('Forecasted Sales',      fc.get('forecasted_sales', ['']*7)),
        ('  Inline Sales',         fc.get('inline_sales', ['']*7)),
        ('  Digital Sales',        fc.get('digital_sales', ['']*7)),
        ('Allowed Hours',          allowed),
        ('  CAP Allowed',          fc.get('cap_allowed', ['']*7)),
        ('  Inline Sales Allowed', fc.get('inline_sales_allowed', ['']*7)),
        ('  Digital Sales Allowed',fc.get('digital_sales_allowed', ['']*7)),
    ]
    allowed_row = None
    for label, vals in summary_fields:
        ws.cell(sr, 1, label)
        if label == 'Allowed Hours': allowed_row = sr
        for d in range(7):
            v = vals[d] if d < len(vals) else ''
            if v != '': ws.cell(sr, _dc(d)[0], v)
        ws.cell(sr, 23, f'=SUM(B{sr}:T{sr})')
        sr += 1

    # Scheduled Hours (paid)
    paid_row = sr
    ws.cell(paid_row, 1, 'Scheduled Hours (paid)').font = BD10
    for d in range(7):
        paid_d = round(sum(_pd(sol[n][d], n) for n in sol), 4)
        ws.cell(paid_row, _dc(d)[0], paid_d).font = BD10
    ws.cell(paid_row, 23, f'=SUM(B{paid_row}:T{paid_row})').font = BD10
    sr += 1

    # Variance Hours
    ws.cell(sr, 1, 'Variance Hours')
    for d in range(7):
        cl = get_column_letter(_dc(d)[0])
        ws.cell(sr, _dc(d)[0], f'={cl}{paid_row}-{cl}{allowed_row}')
    ws.cell(sr, 23, f'=SUM(B{sr}:T{sr})')
    sr += 1

    # Productivity $/Hr
    ws.cell(sr, 1, 'Productivity $/Hr')
    sales_row = last_emp + 3  # Forecasted Sales row
    for d in range(7):
        cl = get_column_letter(_dc(d)[0])
        ws.cell(sr, _dc(d)[0], f'=IF({cl}{paid_row}=0,0,{cl}{sales_row}/{cl}{paid_row})')
    ws.cell(sr, 23, f'=IF(W{paid_row}=0,0,W{sales_row}/W{paid_row})')
    sr += 2

    # Validation table
    ws.cell(sr, 1, 'Final State').font = BD10
    sr += 1
    val_hdrs = ['Day','Var','Open','Lunch','Dinner','Close','2pm','3pm','4pm','9pm','9:30pm','10pm']
    for i, h in enumerate(val_hdrs):
        c = ws.cell(sr, i+1, h); c.font = WB10; c.fill = GRAY
    sr += 1
    for d in range(7):
        var_d = round(sum(_pd(sol[n][d], n) for n in sol) - allowed[d], 4)
        L = sum(1 for n in sol if sol[n][d] and sol[n][d][0]<=12<sol[n][d][1])
        D = sum(1 for n in sol if sol[n][d] and sol[n][d][1]>17)
        O = _O(d); C = _C(d)
        h14=_hd(d,14); h15=_hd(d,15); h16=_hd(d,16)
        cl21=_hd(d,21); cl215=_hd(d,21.5); cl22=_hd(d,22)
        for i, v in enumerate([dn[d], f'{var_d:+.1f}', O, L, D, C, h14, h15, h16, cl21, cl215, cl22]):
            ws.cell(sr, i+1, v)
        sr += 1
    tot = round(sum(_pd(sol[n][d], n) for n in sol for d in range(7)) - sum(allowed), 4)
    ws.cell(sr, 1, 'TOTAL').font = BD10
    ws.cell(sr, 2, f'{tot:+.1f}').font = BD10

    wb.save(out_xlsx)
    print(f"Excel saved → {out_xlsx}")

_out_xlsx = (_base + '.xlsx')
_write_xlsx(_out_xlsx)
