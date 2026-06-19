import json, os
from collections import defaultdict
from ortools.sat.python import cp_model

_OUT = os.environ.get('SCHED_OUT', 'schedule.json')
_base = _OUT[:-5] if _OUT.endswith('.json') else _OUT
_OUT_ACTIVE = _base + '_active.json'
with open('avail_6_29.json') as _f: av=json.load(_f)
with open('reqoff_6_29.json') as _f: req=json.load(_f)
with open('forecast_6_29.json') as _f: fc=json.load(_f)
allowed=fc['allowed_hours']
dn=['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
PB={'John Martin (Jay)','Myles Palmer','Bowen Benedict','James Baker','Trinity Stringer','Gobi Weathers','Mary Dean'}
NO_BREAK={'John Martin (Jay)','Myles Palmer'}
def paid_val(n,a,b):
    r=b-a; return r if n in NO_BREAK else (r-0.5 if r>=5 else r)
TEN_HR=PB|{'Adam Van Bogaert','Mason Doyle','Michael Calderon','Molly Summers','Noah Hiner','Ava Shade','Remi Sullinger','Izzy Simpson','Zac Duffy','Kara Thompson'}
weak3={'Brian Carver','Bryan Bishop','Jason Britt'}
weak5=weak3|{'Layton Angermeier','Emily Owens'}
prep={'Michael Calderon','Tiffany Huffman','Noah Hiner','Gracelyn Dailey','Molly Summers','Reilly Weakley'}
FT_nonleader={'Adam Van Bogaert','Mason Doyle','Michael Calderon','Molly Summers','Noah Hiner','Ava Shade','Izzy Simpson','Remi Sullinger'}

def avwin(n,d):
    w=av[n][d]
    if w=='X' or n in req[dn[d]]: return None
    if w in('any','open'): return [6,23]
    return w
def avail_days(n): return [d for d in range(7) if avwin(n,d)]

fixed={}
def fx(n,d,a,b): fixed[(n,d)]=[a,b]
fx('John Martin (Jay)',0,6,15)
fx('Myles Palmer',0,11,20); fx('Myles Palmer',3,11,20); fx('Myles Palmer',6,11,20)
fx('Myles Palmer',4,12,21); fx('Myles Palmer',5,12,21)
for d in range(5): fx('Bowen Benedict',d,8,16)
fx('Gobi Weathers',0,16,23); fx('Gobi Weathers',1,11,17); fx('Gobi Weathers',2,9,17); fx('Gobi Weathers',5,9,17); fx('Gobi Weathers',6,15,23)
for d in [1,2,3,4,5]: fx('Mary Dean',d,15,23)
fx('Tiffany Huffman',0,9,16)
fx('Trinity Stringer',4,17,23)

ANCH_START=[round(6+0.25*i,2) for i in range(int((18-6)/0.25)+1)]
ANCH_END=[round(13+0.25*i,2) for i in range(int((23-13)/0.25)+1)]
def gen(n,d):
    w=avwin(n,d)
    if not w: return []
    lo,hi=w; out=[]; maxlen=10 if n in TEN_HR else 8
    if n not in PB: lo=max(lo,9)
    if n=='Molly Summers': hi=min(hi,17)
    for a in ANCH_START:
        if a<lo or a>hi-4: continue
        for b in ANCH_END:
            if b<=a or b>hi: continue
            L=b-a
            if L<4 or L>maxlen or (17<b<20) or b in (20.25,20.75): continue
            min_end=15 if d==6 else 14
            if b<min_end: continue
            if n=='Adam Van Bogaert' and b!=23: continue
            out.append((round(a,2),round(b,2)))
    return out

_TH=[9,10,12,14,15,15.5,16,16.5,17,21,21.5,22,22.5]
def _sig(a,b,n):
    s=[a<=t<b for t in _TH]
    s+=[a<=9,a<=10,a<=12,round(a,2)==17.5,round(a,2)==18,round(b,2) in (14,14.5),
        b>=22,b>=22.5,b>21,b>21.5,b>17]
    s.append(round(paid_val(n,a,b)*4)); s.append(round((b-a)*4))
    s.append(round(b,2) if b>=21 else 0)
    s.append(round(a,2) if a<=11.25 else 0)
    return tuple(s)
def dedup(cands,n):
    seen={}
    for (a,b) in cands:
        k=_sig(a,b,n)
        if k not in seen: seen[k]=(a,b)
    return list(seen.values())

people=list(av)
pidx={n:i for i,n in enumerate(people)}
shifts={}
for n in people:
    for d in range(7):
        shifts[(n,d)]=[tuple(fixed[(n,d)])] if (n,d) in fixed else dedup(gen(n,d),n)

# ---- CP-SAT model ----
# All hours scaled by _Q=4 so every value is an integer (1 unit = 15 minutes).
_Q=4
model=cp_model.CpModel()

x={}
for n in people:
    for d in range(7):
        for i in range(len(shifts[(n,d)])):
            x[(n,d,i)]=model.NewBoolVar(f'x_{pidx[n]}_{d}_{i}')

for (n,d) in fixed:
    if (n,d,0) in x: model.Add(x[(n,d,0)]==1)
for n in people:
    for d in range(7):
        if shifts[(n,d)]:
            model.Add(sum(x[(n,d,i)] for i in range(len(shifts[(n,d)])))<= 1)

# SD: pv stored in quarter-hours (integer) for use in hour-based constraints and objective
SD={d:[(n,i,a,b,round(paid_val(n,a,b)*_Q)) for n in people for i,(a,b) in enumerate(shifts[(n,d)])] for d in range(7)}

_trio={'Gobi Weathers','James Baker','Trinity Stringer'}
_no_early={'John Martin (Jay)','Bowen Benedict'}

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
    _SDF[d,'pb_op'] =[x[(n,d,i)] for (n,i,a,b,pv) in sd if n in PB and a<=10]
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
    _SDF[d,'stag9'] =[x[(n,d,i)] for (n,i,a,b,pv) in sd if n not in _no_early and a<=9]
    _SDF[d,'prep9'] =[x[(n,d,i)] for (n,i,a,b,pv) in sd if n in prep and a<=9]

twoTar=[8,8,8,8,8,9,11]; threeTar=[6,6,6,6,7,8,8]; fourTar=[5,5,5,5,6,7,6]
Otar=[6,6,6,6,6,6,6]; Ltar=[9,9,9,9,10,10,11]; Dtar=[10,10,10,11,14,13,12]; Ctar=[5,5,5,5,6,6,6]

for d in range(7):
    h14=sum(_SDF[d,'h14']); h15=sum(_SDF[d,'h15']); h16=sum(_SDF[d,'h16'])
    cl225=sum(_SDF[d,'cl225']); cl21=sum(_SDF[d,'cl21'])
    model.Add(h14>=twoTar[d]);    model.Add(h14<=twoTar[d]+1)
    model.Add(h15>=threeTar[d]);  model.Add(h15<=threeTar[d]+2)
    model.Add(h16>=fourTar[d])
    if d in (0,1,2):
        model.Add(h16<=fourTar[d])
    else:
        model.Add(h16<=fourTar[d]+2)
    model.Add(sum(_SDF[d,'h155'])<=9)
    model.Add(sum(_SDF[d,'h165'])<=8)
    model.Add(sum(_SDF[d,'opener'])==Otar[d])
    model.Add(sum(_SDF[d,'lunch'])>=Ltar[d])
    model.Add(sum(_SDF[d,'dinner'])>=Dtar[d])
    model.Add(cl225>=Ctar[d])
    if d in (4,5):
        model.Add(cl21>=8); model.Add(cl21<=8)
    else:
        model.Add(cl21>=7)
    nineThirtyFloor=7 if d>=4 else 6
    model.Add(sum(_SDF[d,'cl215'])>=nineThirtyFloor)
    model.Add(sum(_SDF[d,'pb_op'])>=1)
    model.Add(sum(_SDF[d,'pb_cl'])>=1)
    if _SDF[d,'w3_ln']: model.Add(sum(_SDF[d,'w3_ln'])<=1)
    if _SDF[d,'w3_dn']: model.Add(sum(_SDF[d,'w3_dn'])<=1)
    for _key in ('la1725','la175','la1775','la18'):
        if _SDF[d,_key]: model.Add(sum(_SDF[d,_key])<=1)
    _cap_8=1 if d in (4,5) else 2
    if _SDF[d,'dep20']:  model.Add(sum(_SDF[d,'dep20'])<=_cap_8)
    if _SDF[d,'dep205']: model.Add(sum(_SDF[d,'dep205'])<=2)
    if _SDF[d,'dep14']:  model.Add(sum(_SDF[d,'dep14'])<=2)
    if _SDF[d,'trio_cl']:model.Add(sum(_SDF[d,'trio_cl'])<=1)
    model.Add(cl225<=Ctar[d]); model.Add(cl225>=Ctar[d]-1)
    if _SDF[d,'stag9']: model.Add(sum(_SDF[d,'stag9'])<=2)
    model.Add(sum(_SDF[d,'prep9'])>=1)

for n in people:
    if n=='John Martin (Jay)': continue
    model.Add(sum(x[(n,d,i)] for d in range(7) for i in range(len(shifts[(n,d)])))<=5)

# All hour constraints in quarter-hours (_Q=4 units per hour)
def hours_q(n):
    return sum(x[(n,d,i)]*round((b-a)*_Q) for d in range(7) for i,(a,b) in enumerate(shifts[(n,d)]))

model.Add(hours_q('Trinity Stringer')>=40*_Q)
model.Add(hours_q('Gobi Weathers')>=37*_Q)
for n in FT_nonleader:
    if len(avail_days(n))>=5:
        model.Add(hours_q(n)>=35*_Q); model.Add(hours_q(n)<=40*_Q)
    else:
        model.Add(hours_q(n)<=40*_Q)
model.Add(hours_q('Adam Van Bogaert')==40*_Q)
model.Add(hours_q('Zac Duffy')>=28*_Q)
for nm,mn in [('Cai Cotton',15),('Hayden Roush',12),('Logan Frias',15)]:
    model.Add(hours_q(nm)>=mn*_Q)
for n in people:
    if n in ('John Martin (Jay)','Myles Palmer'): continue
    model.Add(hours_q(n)<=40*_Q)
model.Add(hours_q('Myles Palmer')>=45*_Q)
model.Add(hours_q('James Baker')>=40*_Q)
model.Add(hours_q('Gracelyn Dailey')>=20*_Q); model.Add(hours_q('Gracelyn Dailey')<=30*_Q)
for _n in ['Shayden Howard','John Dugan','Kayden Anderson','Logan Frias','Richard Raglin',
           'Sandya Wright','Ryder','Oliver Croasdaile']:
    model.Add(hours_q(_n)>=15*_Q)

LEADERS_TW=['Bowen Benedict','James Baker','Trinity Stringer','Gobi Weathers','Mary Dean']
for n in LEADERS_TW:
    for d in [1,2]:
        if shifts[(n,d)]:
            model.Add(sum(x[(n,d,i)] for i in range(len(shifts[(n,d)])))>=1)

for n in weak5:
    model.Add(sum(x[(n,d,i)] for d in range(7) for i in range(len(shifts[(n,d)])))<=2)
model.Add(sum(x[('Bryan Bishop',d,i)] for d in range(7) for i in range(len(shifts[('Bryan Bishop',d)])))<=1)

for n in people:
    for d in range(6):
        nxt=shifts[(n,d+1)]
        if not nxt: continue
        by_end=defaultdict(list)
        for i,(a1,b1) in enumerate(shifts[(n,d)]):
            if b1>=21: by_end[b1].append(i)
        for b1,idxs in by_end.items():
            thresh=b1-12
            early=[j for j,(a2,b2) in enumerate(nxt) if a2<thresh]
            if not early: continue
            model.Add(sum(x[(n,d,i)] for i in idxs)+sum(x[(n,d+1,j)] for j in early)<=1)

zero_pen=[]
for n in people:
    if n in ('John Martin (Jay)','Myles Palmer'): continue
    ad=avail_days(n)
    if not ad: continue
    total_shifts=sum(x[(n,d,i)] for d in range(7) for i in range(len(shifts[(n,d)])))
    z=model.NewBoolVar(f'zero_{pidx[n]}')
    model.Add(total_shifts+z>=1)
    zero_pen.append(z)

# Objective — original: dev_hours + 50*Z + 8*W + 0.3*S
# dev_hours = dev_q/_Q.  Multiply through by 10*_Q=40 to get integer coefficients:
#   40*(dev_q/_Q) = 10*dev_q
#   40*50 = 2000  per zero-shift person
#   40*8  = 320   per weak5 shift
#   40*0.3 = 12   per short shift
total_paid_q=sum(x[(n,d,i)]*pv for d in range(7) for (n,i,a,b,pv) in SD[d])
TARGET_q=round((sum(allowed)+30)*_Q)   # 760.5h → 3042 quarter-hours

for d in range(7):
    day_q=sum(x[(n,d,i)]*pv for (n,i,a,b,pv) in SD[d])
    model.Add(day_q>=round((allowed[d]-3)*_Q))
    model.Add(day_q<=round((allowed[d]+14)*_Q))

dev_q=model.NewIntVar(0,5000,'dev_q')
model.Add(total_paid_q-TARGET_q<=dev_q)
model.Add(TARGET_q-total_paid_q<=dev_q)

weak_use=sum(x[(n,d,i)] for d in range(7) for (n,i,a,b,pv) in SD[d] if n in weak5)
short_pref=sum(x[(n,d,i)] for d in range(7) for (n,i,a,b,pv) in SD[d]
               if n not in NO_BREAK and 5<=(b-a)<=5.5)

model.Minimize(10*dev_q + 2000*sum(zero_pen) + 320*weak_use + 12*short_pref)

print(f'Vars: {len(x)}. Solving with CP-SAT (4 workers, LP linearization)...')
solver=cp_model.CpSolver()
solver.parameters.max_time_in_seconds=240.0
solver.parameters.relative_gap_limit=0.01
solver.parameters.log_search_progress=False
solver.parameters.num_search_workers=4
solver.parameters.linearization_level=2   # full LP relaxation at each node (MIP-like)
status=solver.Solve(model)
status_name=solver.StatusName(status)

if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    actual_paid=sum(solver.BooleanValue(x[(n,d,i)])*pv/_Q for d in range(7) for (n,i,a,b,pv) in SD[d])
    actual_dev=actual_paid-(sum(allowed)+30)
    actual_zeros=sum(1 for z in zero_pen if solver.BooleanValue(z))
    print(f"Status: {status_name} | paid {actual_paid:.1f} | dev {actual_dev:+.1f} | zeros {actual_zeros}")
    sol={n:[None]*7 for n in people}
    for d in range(7):
        for (n,i,a,b,pv) in SD[d]:
            if solver.BooleanValue(x[(n,d,i)]): sol[n][d]=[a,b]
    with open(_OUT,'w') as _f: json.dump(sol,_f)
    with open(_OUT_ACTIVE,'w') as _f: json.dump({n:sh for n,sh in sol.items() if any(sh)},_f)

    def _pd(sh,n):
        if not sh: return 0
        r=sh[1]-sh[0]; return r if n in NO_BREAK else (r-0.5 if r>=5 else r)
    def _hd(d,t): return sum(1 for n in sol if sol[n][d] and sol[n][d][0]<=t<sol[n][d][1])
    def _O(d): return sum(1 for n in sol if n!='John Martin (Jay)' and sol[n][d] and sol[n][d][0]<=10)
    def _C(d): return sum(1 for n in sol if sol[n][d] and sol[n][d][1]>=22.5)
    print(f"{'Day':4}{'Var':>6}  O/L/D/C   2pm/3pm/4pm  9p/930")
    miss=[]
    for d in range(7):
        var=sum(_pd(sol[n][d],n) for n in sol)-allowed[d]
        L=sum(1 for n in sol if sol[n][d] and sol[n][d][0]<=12<sol[n][d][1])
        D=sum(1 for n in sol if sol[n][d] and sol[n][d][1]>17)
        print(f"{dn[d]:4}{var:+6.1f}  {_O(d)}/{L}/{D}/{_C(d)}   {_hd(d,14)}/{_hd(d,15)}/{_hd(d,16)}     {_hd(d,21)}/{_hd(d,21.5)}")
    tot=sum(_pd(sol[n][d],n) for n in sol for d in range(7))-sum(allowed)
    for nm,want in [('Adam Van Bogaert',40),('James Baker',40),('Myles Palmer',45),('Zac Duffy',28)]:
        h=sum((sh[1]-sh[0]) for sh in sol.get(nm,[]) if sh)
        tag='' if abs(h-want)<0.01 or (want==28 and h>=28) else f'  <-- want {want}'
        if tag: miss.append(f'{nm}={h:.1f}{tag}')
    print(f"TOTAL var: {tot:+.1f} | Status {status_name} | wall {solver.WallTime():.1f}s")
    if miss: print("HOUR MISSES:", '; '.join(miss))
else:
    print(f"Status: {status_name} — no solution found")
