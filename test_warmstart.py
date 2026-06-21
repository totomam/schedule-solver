# TEST: warm start via highspy setSolution() with numpy arrays
import json, highspy, numpy as np, time, os
from collections import defaultdict
os.chdir('/home/user/schedule-solver')

with open('avail_6_29.json') as f: av=json.load(f)
with open('reqoff_6_29.json') as f: req=json.load(f)
with open('forecast_6_29.json') as f: fc=json.load(f)
allowed=fc['allowed_hours']
dn=['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
PB={'John Martin (Jay)','Myles Palmer','Bowen Benedict','James Baker','Trinity Stringer','Gobi Weathers','Mary Dean'}
NO_BREAK={'John Martin (Jay)','Myles Palmer'}
def paid_val(n,a,b): r=b-a; return r if n in NO_BREAK else (r-0.5 if r>=5 else r)
TEN_HR=PB|{'Adam Van Bogaert','Mason Doyle','Michael Calderon','Molly Summers','Noah Hiner','Ava Shade','Remi Sullinger','Izzy Simpson','Zac Duffy','Kara Thompson'}
weak3={'Brian Carver','Bryan Bishop','Jason Britt'}; weak5=weak3|{'Layton Angermeier','Emily Owens'}
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
fx('John Martin (Jay)',0,6,15); fx('Myles Palmer',0,11,20); fx('Myles Palmer',3,11,20); fx('Myles Palmer',6,11,20)
fx('Myles Palmer',4,12,21); fx('Myles Palmer',5,12,21)
for d in range(5): fx('Bowen Benedict',d,8,16)
fx('Gobi Weathers',0,16,23); fx('Gobi Weathers',1,11,17); fx('Gobi Weathers',2,9,17); fx('Gobi Weathers',5,9,17); fx('Gobi Weathers',6,15,23)
for d in [1,2,3,4,5]: fx('Mary Dean',d,15,23)
fx('Tiffany Huffman',0,9,16); fx('Trinity Stringer',4,17,23)
ANCH_START=([round(9+0.25*i,2) for i in range(13)]+[round(14+0.25*i,2) for i in range(17)])
ANCH_END=([round(14+0.25*i,2) for i in range(17)]+[round(20+0.25*i,2) for i in range(13)])
def gen(n,d):
    w=avwin(n,d)
    if not w: return []
    lo,hi=w; out=[]; maxlen=10 if n in TEN_HR else 8
    if n not in PB: lo=max(lo,9)
    elif n not in ('John Martin (Jay)','Bowen Benedict'): lo=max(lo,9)
    if n=='Molly Summers': hi=min(hi,17)
    for a in ANCH_START:
        if a<lo or a>hi-4: continue
        for b in ANCH_END:
            if b<=a or b>hi: continue
            L=b-a
            if L<4 or L>maxlen or (18<b<20) or b in (20.25,20.75): continue
            if b<(15 if d==6 else 14): continue
            out.append((round(a,2),round(b,2)))
    return out
_TH=[9,10,12,14,15,15.5,16,16.5,17,21,21.5,22,22.5]
def _sig(a,b,n):
    s=[a<=t<b for t in _TH]; s+=[a<=9,a<=10,a<=12,round(a,2)==17.5,round(a,2)==18,round(b,2) in (14,14.5),b>=22,b>=22.5,b>21,b>21.5,b>17]
    s.append(round(paid_val(n,a,b)*4)); s.append(round((b-a)*4)); s.append(round(b,2) if b>=21 else 0); s.append(round(a,2) if a<=11.25 else 0)
    return tuple(s)
def dedup(cands,n):
    seen={}
    for (a,b) in cands:
        k=_sig(a,b,n)
        if k not in seen: seen[k]=(a,b)
    return list(seen.values())
import pulp
prob=pulp.LpProblem('sched',pulp.LpMinimize); shifts={}; x={}; people=list(av); pidx={n:i for i,n in enumerate(people)}
for n in people:
    for d in range(7):
        shifts[(n,d)]=[tuple(fixed[(n,d)])] if (n,d) in fixed else dedup(gen(n,d),n)
        for i in range(len(shifts[(n,d)])): x[(n,d,i)]=pulp.LpVariable(f'x_{pidx[n]}_{d}_{i}',cat='Binary')
for (n,d) in fixed:
    if (n,d,0) in x: prob+=x[(n,d,0)]==1
for n in people:
    for d in range(7):
        if shifts[(n,d)]: prob+=pulp.lpSum(x[(n,d,i)] for i in range(len(shifts[(n,d)])))<=1
SD={d:[(n,i,a,b,paid_val(n,a,b)) for n in people for i,(a,b) in enumerate(shifts[(n,d)])] for d in range(7)}
_trio={'Gobi Weathers','James Baker','Trinity Stringer'}; _no_early={'John Martin (Jay)','Bowen Benedict'}
_SDF={}
for d in range(7):
    sd=SD[d]
    _SDF[d,'h14']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if a<=14<b]; _SDF[d,'h15']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if a<=15<b]
    _SDF[d,'h155']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if a<=15.5<b]; _SDF[d,'h16']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if a<=16<b]
    _SDF[d,'h165']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if a<=16.5<b]; _SDF[d,'opener']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if n!='John Martin (Jay)' and a<=10]
    _SDF[d,'lunch']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if a<=12<b]; _SDF[d,'dinner']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if b>17]
    _SDF[d,'cl225']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if b>=22.5]; _SDF[d,'cl21']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if b>21]
    _SDF[d,'cl215']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if b>21.5]; _SDF[d,'pb_op']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if n in PB and a<=10]
    _SDF[d,'pb_cl']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if n in PB and b>=22]; _SDF[d,'w3_ln']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if n in weak3 and a<=12<b]
    _SDF[d,'w3_dn']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if n in weak3 and b>17]; _SDF[d,'la1725']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if a==17.25]
    _SDF[d,'la175']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if a==17.5]; _SDF[d,'la1775']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if a==17.75]
    _SDF[d,'la18']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if a==18.0]; _SDF[d,'dep20']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if b==20.0 and n not in PB]
    _SDF[d,'dep205']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if b==20.5 and n not in PB]; _SDF[d,'dep14']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if b in (14,14.5)]
    _SDF[d,'trio_cl']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if n in _trio and b>=22]; _SDF[d,'stag9']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if n not in _no_early and a<=9]
    _SDF[d,'prep9']=[x[(n,d,i)] for (n,i,a,b,pv) in sd if n in prep and a<=9]
twoTar=[8,8,8,8,8,9,11]; threeTar=[6,6,6,6,7,8,8]; fourTar=[5,5,5,5,6,7,6]
Otar=[6,6,6,6,6,6,6]; Ltar=[9,9,9,9,10,10,11]; Dtar=[10,10,10,11,14,13,12]; Ctar=[5,5,5,5,6,6,6]
_CPEN=500; _cov_slk=[]
def _sc(e,cap,t):
    global prob; _s=pulp.LpVariable(t,lowBound=0); prob+=e<=cap+_s; _cov_slk.append(_s)
def _sf(e,fl,t):
    global prob; _s=pulp.LpVariable(t,lowBound=0); prob+=e+_s>=fl; _cov_slk.append(_s)
for d in range(7):
    _h14=pulp.lpSum(_SDF[d,'h14']); _h15=pulp.lpSum(_SDF[d,'h15']); _h16=pulp.lpSum(_SDF[d,'h16'])
    _cl225=pulp.lpSum(_SDF[d,'cl225']); _cl21=pulp.lpSum(_SDF[d,'cl21']); _op=pulp.lpSum(_SDF[d,'opener'])
    prob+=_h14>=twoTar[d]; prob+=_h15>=threeTar[d]; prob+=_h16>=fourTar[d]; prob+=_cl225>=Ctar[d]-1; prob+=_op>=Otar[d]
    prob+=pulp.lpSum(_SDF[d,'lunch'])>=Ltar[d]; prob+=pulp.lpSum(_SDF[d,'dinner'])>=Dtar[d]; prob+=pulp.lpSum(_SDF[d,'cl215'])>=(7 if d>=4 else 6)
    prob+=pulp.lpSum(_SDF[d,'pb_op'])>=1; prob+=pulp.lpSum(_SDF[d,'pb_cl'])>=1; prob+=pulp.lpSum(_SDF[d,'prep9'])>=1
    if d in (4,5): prob+=_cl21>=8
    else: prob+=_cl21>=7
    _sc(_h14,twoTar[d],f'sh14_{d}'); _sc(_h15,threeTar[d],f'sh15_{d}'); _sc(_h16,fourTar[d],f'sh16_{d}')
    _sf(_cl225,Ctar[d],f'scl225f_{d}'); _sc(_cl225,Ctar[d],f'scl225c_{d}'); _sc(_op,Otar[d],f'sop_{d}')
    if d in (4,5): _sc(_cl21,8,f'scl21_{d}')
    _sc(pulp.lpSum(_SDF[d,'h155']),9,f'sh155_{d}'); _sc(pulp.lpSum(_SDF[d,'h165']),8,f'sh165_{d}')
    _cap_8=1 if d in (4,5) else 2
    if _SDF[d,'dep20']: _sc(pulp.lpSum(_SDF[d,'dep20']),_cap_8,f'sdep20_{d}')
    if _SDF[d,'dep205']: _sc(pulp.lpSum(_SDF[d,'dep205']),2,f'sdep205_{d}')
    if _SDF[d,'dep14']: _sc(pulp.lpSum(_SDF[d,'dep14']),2,f'sdep14_{d}')
    if _SDF[d,'trio_cl']: _sc(pulp.lpSum(_SDF[d,'trio_cl']),1,f'strio_{d}')
    if _SDF[d,'stag9']: _sc(pulp.lpSum(_SDF[d,'stag9']),2,f'sstag9_{d}')
    for _key in ('la1725','la175','la1775','la18'):
        if _SDF[d,_key]: _sc(pulp.lpSum(_SDF[d,_key]),1,f's{_key}_{d}')
    if _SDF[d,'w3_ln']: _sc(pulp.lpSum(_SDF[d,'w3_ln']),1,f'sw3ln_{d}')
    if _SDF[d,'w3_dn']: _sc(pulp.lpSum(_SDF[d,'w3_dn']),1,f'sw3dn_{d}')
for n in people:
    if n=='John Martin (Jay)': continue
    prob+=pulp.lpSum(x[(n,d,i)] for d in range(7) for i in range(len(shifts[(n,d)])))<=5
def hours_expr(n): return pulp.lpSum(x[(n,d,i)]*(b-a) for d in range(7) for i,(a,b) in enumerate(shifts[(n,d)]))
prob+=hours_expr('Trinity Stringer')>=40; prob+=hours_expr('Gobi Weathers')>=37
for n in FT_nonleader:
    if len(avail_days(n))>=5: prob+=hours_expr(n)>=35; prob+=hours_expr(n)<=40
    else: prob+=hours_expr(n)<=40
prob+=hours_expr('Adam Van Bogaert')>=35; prob+=hours_expr('Zac Duffy')>=28
for nm,mn in [('Cai Cotton',15),('Hayden Roush',12),('Logan Frias',15)]: prob+=hours_expr(nm)>=mn
for n in people:
    if n in ('John Martin (Jay)','Myles Palmer'): continue
    prob+=hours_expr(n)<=40
prob+=hours_expr('Myles Palmer')>=45; prob+=hours_expr('James Baker')>=40
prob+=hours_expr('Gracelyn Dailey')>=20; prob+=hours_expr('Gracelyn Dailey')<=30
for _n in ['Shayden Howard','John Dugan','Kayden Anderson','Logan Frias','Richard Raglin','Sandya Wright','Ryder','Oliver Croasdaile']:
    prob+=hours_expr(_n)>=15
LEADERS_TW=['Bowen Benedict','James Baker','Trinity Stringer','Gobi Weathers','Mary Dean']
for n in LEADERS_TW:
    for d in [1,2]:
        if shifts[(n,d)]: prob+=pulp.lpSum(x[(n,d,i)] for i in range(len(shifts[(n,d)])))>=1
for n in weak5: prob+=pulp.lpSum(x[(n,d,i)] for d in range(7) for i in range(len(shifts[(n,d)])))<=2
prob+=pulp.lpSum(x[('Bryan Bishop',d,i)] for d in range(7) for i in range(len(shifts[('Bryan Bishop',d)])))<=1
for n in people:
    for d in range(6):
        nxt=shifts[(n,d+1)]
        if not nxt: continue
        by_end=defaultdict(list)
        for i,(a1,b1) in enumerate(shifts[(n,d)]):
            if b1>=21: by_end[b1].append(i)
        for b1,idxs in by_end.items():
            thresh=b1-12; early=[j for j,(a2,b2) in enumerate(nxt) if a2<thresh]
            if not early: continue
            prob+=(pulp.lpSum(x[(n,d,i)] for i in idxs)+pulp.lpSum(x[(n,d+1,j)] for j in early))<=1
zero_pen=[]
for n in people:
    if n in ('John Martin (Jay)','Myles Palmer'): continue
    ad=avail_days(n)
    if not ad: continue
    total_shifts=pulp.lpSum(x[(n,d,i)] for d in range(7) for i in range(len(shifts[(n,d)])))
    z=pulp.LpVariable(f'zero_{pidx[n]}',cat='Binary'); prob+=total_shifts>=1-z; zero_pen.append(z)
total_paid=pulp.lpSum(x[(n,d,i)]*pv for d in range(7) for (n,i,a,b,pv) in SD[d])
for d in range(7):
    day_paid=pulp.lpSum(x[(n,d,i)]*pv for (n,i,a,b,pv) in SD[d]); prob+=day_paid>=allowed[d]-3; prob+=day_paid<=allowed[d]+14
TARGET=sum(allowed)+30; dev=pulp.LpVariable('dev',lowBound=0); prob+=total_paid-TARGET<=dev; prob+=TARGET-total_paid<=dev
weak_use=pulp.lpSum(x[(n,d,i)] for d in range(7) for (n,i,a,b,pv) in SD[d] if n in weak5)
short_pref=pulp.lpSum(x[(n,d,i)] for d in range(7) for (n,i,a,b,pv) in SD[d] if n not in NO_BREAK and 5<=(b-a)<=5.5)
prob+=dev+50*pulp.lpSum(zero_pen)+8*weak_use+0.3*short_pref+_CPEN*pulp.lpSum(_cov_slk)

# Write LP and inject warm start via highspy, then solve using highspy directly
print(f"Vars: {len(x)}. Writing LP and building warm start...")
lp_path='/tmp/sched_warmstart.lp'
prob.writeLP(lp_path)

# Greedy incumbent: assign each person the most-central shift on each available day
greedy_sol={}
for (n,d),ab in fixed.items(): greedy_sol[(n,d)]=shifts[(n,d)][0]
for n in people:
    for d in range(7):
        if (n,d) in greedy_sol or not shifts[(n,d)]: continue
        best=min(shifts[(n,d)],key=lambda ab: abs((ab[0]+ab[1])/2-14))
        greedy_sol[(n,d)]=best

h=highspy.Highs()
h.silent()
h.readModel(lp_path)
n_cols=h.getNumCol()
h_var_names=[h.getColName(i)[1] for i in range(n_cols)]
name_to_col={name:i for i,name in enumerate(h_var_names)}
sol_arr=np.zeros(n_cols,dtype=np.float64)
for n in people:
    for d in range(7):
        if (n,d) not in greedy_sol: continue
        chosen=greedy_sol[(n,d)]
        for i,(a,b) in enumerate(shifts[(n,d)]):
            if (a,b)==chosen:
                vname=f'x_{pidx[n]}_{d}_{i}'
                if vname in name_to_col: sol_arr[name_to_col[vname]]=1.0
                break
col_idx=np.where(sol_arr>0.5)[0].astype(np.int32)
col_val=sol_arr[col_idx]
ws_result=h.setSolution(len(col_idx),col_idx,col_val)
print(f"Warm start injected ({len(col_idx)} non-zeros, setSolution={ws_result}). Solving...")
h.setOptionValue('time_limit',240.0)
h.setOptionValue('mip_rel_gap',0.01)
t0=time.time()
h.run()
elapsed=time.time()-t0
ms=h.getModelStatus()
obj=h.getInfoValue('objective_function_value')[1]
gap=h.getInfoValue('mip_gap')[1]
zeros_count=0  # can't easily extract from raw highspy without var mapping
print(f"Status: {h.modelStatusToString(ms)} | obj={obj:.2f} | gap={gap:.6f} | time={elapsed:.1f}s")
print(f"real\t{int(elapsed//60)}m{elapsed%60:.3f}s")
