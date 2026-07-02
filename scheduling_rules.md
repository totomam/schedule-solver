# Paddock Schedule Rules

Complete reference for building the weekly schedule. Given availability sheet, request-off book, and sales forecast — apply these rules to produce the schedule.

---

## 1. INPUTS NEEDED EACH WEEK

1. **Availability sheet** (PDF/text listing each employee's avail per day)
2. **Request-off book** (notebook page with names handwritten under each day of the week)
3. **Sales forecast** with allowed hours per day (Forecasted Sales, Inline, Digital, Allowed Hours, CAP Allowed, Inline Sales Allowed, Digital Sales Allowed)

---

## 2. HOURS RULES

### Manager hours (set defaults — only override when explicitly needed)
- **Jay Martin**: Standard 45h. Mon 6a–3p, Thu 10a–8p, Fri 10a–8p, Sat 10a–8p, Sun 11a–5p. Off Tue/Wed normally.
- **Myles Palmer**: Standard 45h. Mon & Sun 12p–9p; Tue/Wed/Sat 11a–8p. Off Thu/Fri normally. Shifts automatically adjust to 2p–11p on any day he is needed as the only PB closer.
- Both managers have backbone shifts set each week by the solver. The backbone auto-adjusts: if no other PB member can open on a given day, Jay's shift slides earlier (≤9am); if no other PB member can close, Myles's shift slides later (2pm–11pm). No manual action needed.

### Non-manager hour caps
- **Maximum 40h** for everyone except Jay and Myles (NO OVERTIME — we don't pay it)
- **Minimum shift length: 4 hours**
- **Part-time shifts capped at 8 hours per shift.** Only full-time, shift leaders, managers, and the blanket-approved 10h people (see below) may be scheduled longer than 8h. If a PT shift over 8h is genuinely needed, get manager permission first and log it as a one-time exception.
- **10-hour-OK people** (may work up to 10h without asking): all leaders/managers (Bowen, James, Trinity, Gobi, Mary, Jay, Myles), plus Adam, Mason, Ava, Remi, Izzy, Zac, Kara Thompson. Keegan will be added once onboarded. Note: Molly, Noah, Reilly, and Michael are capped at 5pm by availability so 10h shifts aren't applicable to them. Other PTs need explicit one-time manager approval for anything over 8h.
- **Maximum 5 days per week for everyone, including Jay and Myles.** Nobody is scheduled more than 5 days.

### Paid vs unpaid breaks
- **Paid breaks (no deduction)** — these people get hours as-is:
  - Managers ONLY: Jay Martin, Myles Palmer
- **Everyone else, INCLUDING the 5 shift leaders** (Bowen Benedict, James Baker, Trinity Stringer, Gobi Weathers, Mary Dean): subtract 0.5h from any shift ≥ 5 hours. The shift leaders clock out for a 30-min unpaid break like all hourly staff.
  - Example: 8a-4p (8h raw) shows as 7.5 paid
  - Example: 4:30p-9p (4.5h raw) shows as 4.5 paid (under 5h = no deduction)
- Per-person cells in the .xlsx show FULL (raw) hours; the bottom "Scheduled Hours (paid)" row shows paid totals after break deductions. This paid model is the correct basis for planning.

### 11pm closers counted as 10:45 in paid hours
- **A closer scheduled until 11:00pm is counted as 10:45pm (22.75) in paid hours** — they almost always finish closing duties and clock out ~10:45 (a −0.25h deduction, same principle as the 30-min break, on top of it).
- This is built into `paid_val`, so it applies **everywhere paid hours are used, including the weekly/daily labor budget band**. Effect: the solver treats each 11pm closer as 0.25h cheaper, so it has ~4h/week more clock time to schedule against the same budget.
- The schedule (per-person cells and the printed grid) still **SHOWS** the 11pm end — only the paid/variance math uses 10:45. Target/floor hours are unaffected (those use raw clock hours, not paid).

### FT target hours (raw hours)
- Shift leaders (Bowen, James, Trinity, Gobi, Mary): **39–40h raw**. Gobi is capped at ~37h raw by her fixed schedule and the 12h close-then-open rule — she's the exception.
- Other FT non-leaders (Adam, Mason, Michael, Molly, Noah, Ava, Izzy, Remi): **33–40h raw**
- Zac Duffy: **30h target, no hard cap** (penalty for missing it; generic 40h ceiling applies above that)
- Reilly Weakley: **hard-capped at 3 shifts/week — 24h target**, not the standard 33-40h FT band (see §10)

---

## 3. SCHEDULING CONSTRAINTS

### Jay-specific (default set schedule)
- **Off Tuesday AND Wednesday** normally
- **Mon 6a-3p** (9h) — admin time at open, doesn't count as opener
- **Thu/Fri/Sat 10a-8p** (10h)
- **Sun 11a-5p** (6h)
- **Standard total: 45h raw**
- **Strongly penalized for taking closing shifts** (end 11pm) — will only close in an extreme edge case where no other PB member can close and Myles is also unavailable. Not a hard rule, but effectively never happens.
- **Never schedule a 9a-9p (12h) shift** — exceeds the 10h max
- Override default only when you explicitly need to (e.g., a one-off week covering 6 days)

### Myles-specific (default set schedule)
- **Mon & Sun: 12p–9p; Tue, Wed, Sat: 11a–8p** (9h each)
- **Off Thu, Fri**
- **Default total: 45h raw**
- **Shifts to 2p–11p** automatically on any day he is the only PB member who can close that night
- **Strongly penalized for taking opening shifts** (start ≤10am) — priority closer, not opener
- Override default only when explicitly needed

### Manager deviation rules

**Rule 1 — Day swap when a manager requests off a working day:**
- If **Jay** requests off Thursday or Friday → Myles covers that day instead. Myles then takes a different day off (not his usual Thu/Fri). Jay works Myles's normal off day (Thu or Fri) in exchange.
- If **Myles** requests off Tuesday or Wednesday → Jay covers that day instead. Jay then takes a different day off (not his usual Tue/Wed). Myles works Jay's normal off day (Tue or Wed) in exchange.
- Goal: manager hours stay whole (45h / 45h). The avail JSON for that week reflects the swap — open the covering manager on the new day, mark the requesting manager's original day X.

**Rule 2 — Coverage backstop when leaders can't cover open or close:**
- If shift leaders request off or are otherwise unavailable in a way that leaves a day without a leader opener (≤9am) or closer (≥10pm), a manager covers that slot.
- **Jay is the priority OPENER** (penalised for taking closing shifts). **Myles is the priority CLOSER** (penalised for taking opening shifts). If the preferred manager is also unavailable, the other covers.
- The solver handles this automatically via the backbone: `_pb_opener_exists(d)` and `_pb_closer_exists(d)` are evaluated at model-build time, and manager backbone shifts slide to cover gaps. No manual action needed unless you're building by hand.

**Rule 3 — Both managers off the same day:**
- If both Jay AND Myles are unavailable on the same day (req'd off or avail="X"), **every shift leader who IS available that day must work** — no shift leader may request off that day. This guarantees the day always has PB coverage for open and close.
- In the request-off book: if Jay and Myles are both off a day, do not write any shift leader name under that day.
- The solver enforces this as a hard constraint and the test protocol blocks the scenario from being generated.

### Close-then-open rule
- **Minimum 12 hours between close and next-day open**
- Example: 11pm close → 11am next day open = ✓ (12h gap)
- Example: 11pm close → 10am next day open = ❌ (only 11h)

### Leader coverage
- **Every day MUST have a shift leader or manager opening AND closing — a hard floor, enforced by the solver (infeasible if unmet), not a preference.**
- Opening = a PB member working at or before 9am
- Closing = a PB member working until 10pm or later
- Leaders/managers available to anchor open & close: Jay, Bowen, James, Trinity, Gobi, Mary. Plan leader coverage around each leader's days off and any request-offs that week.
- If no leader is available to close on a given day (rare): Myles automatically shifts to close as a backstop.

---

## 4. REQUEST-OFFS & AVAILABILITY (CRITICAL — audit after every change)

- **Availability sheet** = source of truth for when each person CAN work
- **Request-off book** = source of truth for who CAN'T work that specific day
- Read **every name on every day** carefully — names can appear on multiple days
- After any schedule change, **audit BOTH**:
  1. Against the request-off book (names off specific days)
  2. Against the availability sheet (shifts within each person's hours and on days they're available)
- "X" or "xx" in availability = not available that day
- Names commonly off all-week or multi-day get fully removed from those days

---

## 5. COVERAGE TARGETS

### Openers (people working at or before 10am)
- **Jay is NEVER counted as an opener, on any day** (admin time). All opener counts and targets below exclude Jay. The summary chart's "Open" column also excludes Jay, so the printed number matches these targets.
- **HARD: exactly 3 people in by 9:00, counting Bowen's 8a anchor** (so Mon–Fri that's Bowen + 2 others at 9:00; on weekends when Bowen is off it's 3 others at 9:00), **and exactly 2 more starting at exactly 10:00.** Both counts are hard floors AND ceilings enforced by the solver — 5 openers total every day, Monday through Sunday, split precisely 3-by-9 / 2-at-10.
- **No stagger between 9:00 and 10:00 anymore.** The old 9:15/9:30/9:45 stagger option is gone — nobody may start in that window at all. An opener's only two valid start times are "at or before 9:00" or "exactly 10:00."
- **No one may start between 10:00am and 11:00am.** The next valid start slot after 10:00 is 11:00am. Starts at 10:15, 10:30, and 10:45 are banned.

### Lunch (people working at noon)
- **Hard floor per day:** Mon–Thu = 9, Fri/Sat/Sun = 10. The solver must meet these or report the week infeasible — it never returns a schedule below the lunch floor.
- **Sunday aims for 11** as a *soft* target: a penalty for sitting at 10 (the hard floor), not a failure. Flagged as `LunchTargetMiss` when it can't reach 11.

### Closers (people working past 10:30pm — i.e., to 11pm close)
- **Target: 5 closers every day of the week (no more weekend bump to 6). HARD floor at target-1 (4) — 2+ below is now infeasible, not just penalized:**
  - **1 below target (4): large penalty, still allowed.** Human preference: 4 closers should be rare, not a routine thin-day outcome — weighted between the lunch soft target and the trio-cap escape valve, so a thin day gives up other tradeoffs (coverage ceilings, hour floors, even the Sunday lunch-11 target) before settling for 4. Flagged `CloserTargetMiss`.
  - **2+ below target (3): INFEASIBLE.** The solver will report the week as unsolvable rather than field this few closers.
- Do not run *more* than the target — too many closers was a recurring problem (soft ceiling).
- **Mary Dean always closes on every day she's available, except 1 (hard rule, enforced by the solver — not a preference).** She works all but 1 of her available days, and every day she works is a close.
- **James Baker never closes on the same day as Mary Dean (hard rule).** Move James to a mid or open shift instead — he does not close that day.
- **Absent Mary (she's off that day), the old rule still applies as a strong preference: never more than one of Gobi, James, or Trinity closing the same day.** This is no longer strictly hard — it's a very high-penalty soft rule that may be broken **only** as a last resort when the hard closer floor above genuinely cannot be met any other way. When Mary *is* closing, Gobi and Trinity may freely join her — only James is excluded (that part stays hard).

### Evening staffing floor (every day)
- **9pm: at least 7 people still working past 9:00pm Mon–Thu and Sun.**
- **Friday & Saturday: hold the past-9pm count at exactly 8** — floor of 8, but capped at 8. To keep it from ballooning (the heavy Fri/Sat dinner crew would otherwise leave ~10 people on past 9), push the surplus dinner-crew shifts to **end at exactly 9:00pm**, since a 9:00 end does not count as "past 9pm." This raises the effective evening floor to 8 while trimming late-evening labor.
- **9:30pm: at least 6 people working past 9:30pm Monday–Thursday; at least 7 Friday–Sunday.**
- Counting follows the standard convention: a person counts toward a time only if they're working *past* it (a shift ending exactly at 9:00pm does not count toward the 9pm floor).
- This is broader than the closer count (closers work to 10:30/11pm); it keeps enough hands on the floor through the back half of the dinner rush before close.

### Dinner (people starting at/before 6pm AND ending at/after 8pm)
- **Both conditions are required, not just a late end.** Someone who works a lunch/midday shift ending at 5, 6, or 7pm does NOT count as dinner, even though they worked into the evening — they have to still be on the floor at 8pm. (Previously this was defined as simply "ends after 5pm"; tightened per human request so "working dinner" means genuinely covering the dinner rush, not just a late-afternoon departure.)
- **Hard floor per day** (see table below): Mon–Wed 10, Thu 11, Fri 13, Sat 13, **Sun 11**. The solver must meet these or report the week infeasible. (Sunday matches Thursday's 11, not the generic 10 — human preference: Sunday reliably hitting 11 outranks Thursday reaching a 12th body.)
- **Every day** has a *tiny* soft aspiration of hard-floor+1 — a nice-to-have nudge only, deliberately weighted far below every other coverage penalty. Flagged `DinnerTargetMiss` when a day sits at the floor instead of floor+1.
- **Known risk accepted:** under this tighter definition, Friday and Saturday's floor of 13 has essentially zero slack — even a perfectly-staffed week with no req-offs maxes out at exactly 13. Any req-off that removes a dinner-eligible person on those days can push the week into a genuine infeasibility that wouldn't have happened under the old, looser definition. This is a known, accepted tradeoff, not a bug — confirmed via stress testing before shipping.

### Lunch/Dinner targets by day
*(may shift week-to-week based on forecasted sales — these are the current working targets)*

| Day | Lunch / Dinner (hard floor → tiny aspiration) |
|-----|---------------|
| Monday | 9 / 10→11 |
| Tuesday | 9 / 10→11 |
| Wednesday | 9 / 10→11 |
| Thursday | 9 / 11→12 |
| Friday | 10 / 13→14 |
| Saturday | 10 / 13→14 |
| Sunday | 10→11 / 11→12 |

Every day's lunch and dinner number is a **hard minimum**. Above that, dinner adds a tiny floor+1 aspiration on every day (see above); lunch keeps its own separate, much larger soft aspiration on Sunday only (aims for 11, `_LUNCHPEN`).

**The hard floors are enforced as hard constraints:** the solver must meet every day's lunch and dinner hard floor or report the week infeasible (a fail) — it never returns a schedule that quietly misses one. The Sunday lunch soft target (11) is penalised, not hard, so a depleted Sunday may sit at the floor. When a thin roster forces a choice, the hard meal floors take priority over the afternoon headcount ceilings (2pm/3pm/4pm) — the afternoon may run over its target to keep the lunch crew working through to dinner.

### Coverage priority hierarchy (when a thin day forces tradeoffs)
From highest to lowest, what the solver protects first:
1. **Hard floors** (infeasible if unmet): lunch floor, dinner floor, exact opener timing (3@9/2@10), closer floor at target-1, at least 1 PB opener AND 1 PB closer per day, ≥1 shift for every available person, James-never-with-Mary. Plus the manager and weekly-budget hard bounds.
2. **Trio-cap escape valve:** breaking "at most 1 of Gobi/James/Trinity" (absent Mary) — a very high penalty, paid only when it's the sole way to meet the hard closer floor above.
3. **Closer target miss:** sitting at 4 closers (1 below the 5 target) — a large penalty, just below the trio-cap escape valve.
4. **Lunch soft target** (Sunday 11).
5. **Small penalty:** the tiny per-day dinner+1 aspiration. Roughly tied with the afternoon over-staffing ceilings.

---

## 6. VARIANCE TARGETS (paid hours over allowed hours)

| Day | Variance Target |
|-----|------------------|
| Monday | +5 |
| Tuesday | +5 |
| Wednesday | +5 |
| Thursday | +8 |
| Friday | +15-20 |
| Saturday | +15-20 |
| Sunday | +10-15 |

**Weekly target: total scheduled variance for the week is +25 to +30 over base allowed hours.** Any value in that range is acceptable — don't chase a single number. Individual day variances will vary (busy days like Fri/Sat/Sun carry more, slow days less). Lower variance from a genuinely thin roster is acceptable and reflects real availability, not under-scheduling.

---

## 7. EMPLOYEE PRIORITY TIERS

**When multiple people are competing for the same scarce leftover hours** (a heavy req-off week
thins out who's available, and there aren't enough hours to fully satisfy everyone's target),
the solver fills tiers in this order, most-essential first: **shift leaders/managers → FT
non-leaders → Strong PT → Middle/Regular PT → Weak/limited group.** This also applies when
someone's own availability shrinks below what their normal weekly target needs — rather than
giving up on their hours entirely, the solver pushes them as close to what THEIR available days
can actually support as possible, at the same priority as their tier.

### Strong PT (give more hours, 20h+ target)
- Cai Cotton
- Diana Castaneda — new hire, joining as of this schedule. Available any Mon-Sat, 12p-11p Sunday.
- Kara Thompson
- Nathan Paaswee
- Peyton Shaw
- Reese Bezehertny
- Sandy Wright
- Gracelyn Dailey — **30h target (not the standard 20h), no hard cap, penalty for missing it.** Availability changes every month and is NOT in the standard availability sheet. She prints and brings her own calendar. Always verify her current availability before each build; do NOT assume she's "any"/open. (Example: for 6/22-6/28 she was available Saturday only.)

### Weak / limited group — "don't pull their weight," spread out, prefer one day each
- **Full group (all seven): Emily Owens, Brian Carver, Bryan Bishop, Jason Britt, Shayden Howard, Oliver Croasdaile, John Dugan**
- **Prefer-one-day rule (applies to ALL SEVEN):** schedule each of them just one day/shift per week when possible. Only give a second day if coverage genuinely requires it (hard cap of 2 days/week per person, enforced by the solver). **Exception: Bryan Bishop is hard-capped at 1 day/week** (`WEAK5_MAX_DAYS` override in `backbone.py`), not 2.
- **One-per-meal-period rule (applies ONLY to Brian Carver, Bryan Bishop, Jason Britt):** never more than ONE of these three working the same meal period (lunch or dinner) on any given day. Lunch = on the floor at noon; dinner = starting at/before 6pm AND ending at/after 8pm. Each lunch and each dinner across the week may contain at most one of them. (One-per-meal exceptions can be approved individually.)
- Spread them across the week rather than clustering. Prefer stronger people on the busy days (Fri/Sat/Sun) and use these seven to fill genuine gaps.

### Middle PT (use as needed for coverage, 12h target)
- Kayden Anderson, Amiyah Bartley, Logan Frias, Richard Raglin, Harper Flynn, Jonathan Beacham, Hayden Roush
- **Ryder**: new hire, available any day/time, PT standard (max 8h shifts, takes break, max 5 days per week)

### New / occasional
- **Jacob Cothern**: PT, 2 shifts only, available Mon-Thu 5p-9:30p (dinner shifts). Place on the higher-volume of his available days.
- **Zac Duffy**: college kid (CK), cleared for 10h shifts. **30h target, no hard cap, penalty for missing it** (falls under the generic 40h ceiling like everyone else). Available Mon/Tue/Thu/Sun.
- **Keegan**: cleared for 10h shifts. Add to avail JSON when onboarded.

### Leaving / on way out
- Get 1-2 shifts max, no need to prioritize hours

### Special cases
- **Sienna Underwood**: no availability listed, generally skip
- **Hayden Roush**: depending on week — may request off entirely
- **Sandy Wright**: weekdays-only normally (school); summer break may change
- **Tiffany Huffman**: set schedule Mon 9a–4p only (backbone-fixed). No hours floor — backbone handles her one shift.
- **Izzy Simpson**: FT non-leader, 33–40h target

---

## 8. SHIFT LENGTH OPTIMIZATION

### 15-minute increment in/out times (standing rule)
- **Shift start and end times may be set on any 15-minute increment** (e.g. 9:15a, 10:45a, 2:15p, 3:45p) throughout the entire day, not just on the hour or half-hour.
- This lets staffing track demand more precisely and squeezes out rounding waste — people start and end closer to when they're actually needed.
- Applies across the whole operating day (open through close), in addition to the forbidden end times (no 6pm/7pm ends, nothing ending before 2pm / 3pm Sunday) and the 4-hour minimum shift length.

### The "just under 5 hours" trick
- A 4.5h shift = 4.5 paid hours (no break)
- A 5h shift = 4.5 paid hours (after break)
- **Same paid hours, but 5h shift gives more coverage**
- Use 4-4.5h shifts when you want to give a PT hours WITHOUT eating into labor budget
- Prefer 4-4.5h shifts over 5-5.5h shifts: same labor, no break to manage, and it spreads people across more days (shorter shifts, more days).
- Use 5h+ when you NEED the extra coverage

### Common odd-time starts to dodge break
- 9:15a start (4.25h or 4.75h shift)
- 4:30p start
- 5:30p start
- 11:30a start

### Common shift structures
- **Strong PT closer**: 4:30p-10:30p (6h raw, 5.5 paid) or 5p-10:30p (5.5h raw, 5 paid)
- **Mid PT closer**: 5p-9p (4h no break) or 5:30p-10p (4.5h no break)
- **Lunch shift**: 9a-2p (5h, 4.5 paid) or 9:15a-2p (4.75h no break)
- **Long lunch/midday**: 11a-5p, 9a-4:30p, 10a-3pm

---

## 9. STAGGERING (best practices)

### Before 9am — managers & shift leaders ONLY
- **No one except managers and shift leaders may start before 9:00am.** Everyone else starts at 9:00am or later.
- The only people scheduled before 9am: **Jay** (Mon 6a), **Bowen** (8a Mon-Fri), **Gobi** (Saturday 8a), **Trinity** (Saturday, if needed), **James** (Sunday 8a). No one else.

### Morning starts
- Opener count and start times: see **§5 → Openers** (the single source for the hard 3-by-9 / 2-at-exactly-10 rule and the 10:01–10:59 ban). The notes below add only the staffing detail.
- At least one prep person (Michael, Tiffany, Noah, Gracelyn, Molly; Reilly = dough on Sunday) should be among the 9:00 starters.
- Bowen anchors morning at 8a (set schedule)

### Afternoon transitions
- 3p-5p transition window: stagger so coverage doesn't spike
- Use 3p, 3:30p, 4p, 4:30p, 5p, 5:30p starts

### Openers — cap (not counting Jay)
- The definition (start ≤10am, Jay never counts) and the hard floor/ceiling of 5 live in **§5 → Openers**.
- If a day is running over 5, push the extra early-starters to an 11am start — they still cover lunch and dinner, they're just no longer openers. (Nothing may start 10:01–10:59; the next slot is 11:00.)

### Afternoon headcount (2pm / 3pm / 4pm) — HARD TARGETS
- **These are targets to hit exactly, not a guide** (enforced as heavily-penalized soft floor+ceiling pairs, `_CPEN=500` — not literal hard-infeasibility floors like lunch/dinner/openers, but weighted so slack is always 0 in the optimal solution, i.e. hit exactly in practice):
  - **Normal days (Mon–Thu): 2pm = 8, 3pm = 6, 4pm = 5**
  - **Friday: 2pm = 8, 3pm = 7, 4pm = 6**
  - **Saturday: 2pm = 9, 3pm = 8, 4pm = 7**
  - **Sunday: 2pm = 11, 3pm = 8, 4pm = 6**
- **Counting convention (applies to ALL headcount counts at every clock time):** a person counts toward the headcount at time T only if they are still working *past* T. If their shift ends exactly at T, they do NOT count toward T — they're considered gone. (Floor at T = shifts with start ≤ T AND end > T.) So someone ending at exactly 3:00 counts at 2pm but not 3pm.
- Build the afternoon to land on these numbers. The 3-5pm peak ceiling still applies (≤8 normal/Fri/Sat; Sunday's 2pm/3pm run higher by design). **Exception:** these afternoon ceilings yield to the hard lunch/dinner minimums — on a thin day the afternoon may run over target to keep the lunch crew on through to dinner.
- Mechanics for hitting them cleanly: extend or trim daytime (lunch) shifts to control the 2pm and 3pm counts; stagger when the dinner crew starts (3/4/5pm) to control 3pm and 4pm; this also lets you push saved afternoon hours into dinner and weekend coverage.

### Departure timing
- **No one leaves before 2pm** on any day — this is a hard rule with no exceptions. The earliest any non-Sunday shift may end is 2:00pm.
- **At most 2 people leave at 2:00pm or 2:30pm on any given day.** Don't bunch departures — spread the early-out shifts so no more than two end in that 2:00/2:30 window.
- **Sunday: no one leaves before 3pm.** The earliest any Sunday shift may end is 3:00pm. To make the Sunday afternoon drop (11 → 8), send exactly 3 people home *at* 3:00 (they end at 3:00, so they count at 2pm but not 3pm).
- Forbidden end times: **no shift may end strictly between 6:00pm and 8:00pm** (6:00pm and 8:00pm themselves are fine; ends at 6:15, 6:30, … 7:45 are banned) — unless a shift is specifically pinned otherwise. Also none before 2:00pm (3:00pm Sunday).
- **Evening-departure stagger:** no one ends at 8:15pm or 8:45pm (banned). At most **2 people end at 8:00pm** and **2 at 8:30pm** — except Friday & Saturday, where at most **1 ends at 8:00pm**. (Managers/leaders on fixed shifts are exempt from these counts; the caps govern the flexible staff the solver places.)

### Shift end times — NEVER end at 6pm or 7pm
- **Do not schedule anyone to leave between 6:00pm and 8:00pm** (exclusive) — that's the dinner ramp and rush. A shift should either end at **6:00pm or earlier** (a lunch/midday body, off before dinner ramps) OR **8:00pm or later** (a dinner body that works through the rush). The only exception is a shift specifically pinned to end in that window.
- When shortening a dinner shift to save hours, pull it back to 6pm; when extending a midday shift, push it to 8pm+

### Evening closes
- **Closer end-time distribution (target for each day):**
  - 2 people until 11:00pm
  - 2 people until 10:30pm
  - 1 person until 10:15pm
  - 1 person until 10:45pm
- On 5-closer days (every day now) the solver will naturally drop one slot (typically 10:45pm).
- **Adam always ends at 11:00pm** (set pattern, Mon-Fri). Enforced in solver gen().
- **All PB (shift leaders AND managers Jay/Myles): if on a closing shift (end ≥ 10pm), must end at exactly 11pm** — leaders are in charge and stay until close; managers on closing backup do the same. Enforced in solver gen().
- Mary: solver places her freely Mon–Fri; **Saturday only** is pinned as a 3–11pm close.
- **Late-arrival caps: at most 1 person may start at each of 5:15pm, 5:30pm, 5:45pm, and 6:00pm** (one per slot, four separate caps). Don't stack late dinner starts — spread evening arrivals across earlier start times.

---

## 10. FT WEEKLY STRUCTURE (defaults)

### Set schedules (don't change without reason)
- **Bowen**: Mon-Fri 8a-4p — **always a full 8a-4p, every day he works. Never short his hours** (don't trim him to 8-3, etc.)
- **Adam**: Mon-Fri, **always ends at 11pm** (e.g. 4p-11p, or starts earlier when more hours are needed). Adam never ends before 11pm. **Weekend make-up**: if he requests a weekday off, he becomes available for his usual 1p-11p pattern on Sat and/or Sun instead, so he can still hit his hours — only on a weekend day he hasn't also requested off. Automatic in the solver (`WEEKEND_MAKEUP` in `backbone.py`); doesn't require editing his weekend `avail.json` entries by hand.
- **Mary**: Sat 3p-11p (pinned); every other available day is solver-placed as a close, all but 1 of her available days (see §5 → Closers).
- **James**: any most days, Wed 3-11, Sun 8-4. **Never closes on the same day as Mary Dean**; absent Mary, does not close alongside Gobi or Trinity either (move him to mid/open that day). See §5 → Closers for the full rule.
- **Trinity**: rotates between AM and PM days; usually Mon 9-4, Tue 2-11, Wed any, Thu any, Fri 5-11, Sat 9-4, Sun off
- **Gobi**: Mon 4-11, Tue 11-5, Wed 9-5, Sat 8-4, Sun 3-11. **Tuesday opens at 11a (not 10a)** — opening earlier would break the 12-hour rule after her Monday 11pm close.
- **Michael**: M-F 9-5 (limited by 2nd job — sometimes ~3 days)
- **Molly**: any/prefers days. **Never works past 5pm** — every Molly shift ends at 5:00pm or earlier.
- **Noah**: M-F 9-5 area, often using 9:15 start trick
- **Ava**: any, prefers mornings (FT)
- **Mason**: any 10-10, varied shifts
- **Reilly**: max 3 shifts, prefers 9-5. Hard shift-count cap (enforced in solver), 24h target — not the standard FT 33-40h band (see §7).
- **Remi (kitchen)**: 9a-11p avail M/T/Th/F/Sat. Works afternoon/evening prep shifts (3p-11p typical), NOT late-night close

---

## 11. PROCESS CHECKLIST (in order)

When building a new schedule:

1. **Lock in mandatory hours**:
   - Jay = 45h standard (Mon 6–3, Thu/Fri/Sat 10–8, Sun 11–5); off Tue/Wed normally
   - Myles = 45h standard (Mon & Sun 12–9, Tue/Wed/Sat 11–8); off Thu/Fri normally
   - Shift leaders aim for 39–40h raw (Bowen, James, Trinity, Gobi, Mary)

2. **Add FT regulars** at their set patterns (Bowen, Adam, Mary, Michael, etc.)

3. **Add strong PT** with 20h+ each, spread across days

4. **Fill coverage gaps** using middle PT

5. **Apply the weak/limited group** (Emily, Brian, Bryan, Jason) — one shift each where possible; keep Brian/Bryan/Jason to one per meal period

6. **Validate**:
   - [ ] All request-offs honored (cross-check against book line-by-line)
   - [ ] All shifts within each person's availability (cross-check avail sheet; verify Gracelyn's monthly calendar)
   - [ ] Every day has leader open (PB member ≤9am) AND close (PB member ≥10pm)
   - [ ] Mary Dean closes all but 1 of her available days (hard); James never closes with Mary (hard); absent Mary, at most ONE of Gobi/James/Trinity closes per day (soft escape valve — may break only if the closer floor needs it)
   - [ ] No close-then-open under 12h (incl. leaders — Gobi opens Tue at 11a)
   - [ ] No hourly over 40h; Adam exactly 40 and always ends 11pm; FT non-leaders 33-40h; Zac 30-35h
   - [ ] No one starts before 9am except Jay/Bowen/Gobi(Sat)/Trinity(Sat)/James(Sun)
   - [ ] No one leaves before 2pm; Sunday no one leaves before 3pm
   - [ ] ≤2 people leave at 2:00/2:30pm; ≤1 person starts at each of 5:15/5:30/5:45/6:00pm
   - [ ] Molly never past 5pm
   - [ ] 2/3/4pm hard targets hit exactly (Mon-Thu 8/6/5; Fri 8/7/6; Sat 9/8/7; Sun 11/8/6)
   - [ ] Lunch ≥ hard floor (Mon–Thu 9, Fri/Sat/Sun 10; Sun aims 11); dinner ≥ hard floor (Mon-Wed 10, Thu/Sun 11, Fri/Sat 13; every day has a tiny +1 aspiration)
   - [ ] Openers (Jay never counts): hard exactly 3 in by 9:00 + exactly 2 at exactly 10:00 (Bowen-counts detail in §5 → Openers). No starts 9:01–9:59 or 10:01–10:59. Closers target 5/day (every day) — hard floor at target-1 (4), large penalty for sitting exactly 1 below
   - [ ] Every available person gets at least one shift (hard, unless they have zero available days)
   - [ ] Weekly total variance lands in the +25 to +30 range (paid hours over allowed)
   - [ ] No shift under 4h

7. **Build the .xlsx** in reference format (employee rows alphabetical, with Schedule Summary at bottom)

---

## 12. ALPHABETICAL NAME MAP (printed schedule vs. nicknames)

| Printed | Goes by |
|---------|--------|
| Jay Martin | Jay |
| Claire Cotton | Cai |
| Danielle Sullinger | Remi |
| Kyle Summers | Molly |
| Lucas Baker | James |
| Noah Weathers | Gobi |
| Sandy Wright | Sandy |
| Izabella Simpson | Izzy |

(In the .xlsx schedule, use the "goes by" name — Jay, Cai, Remi, etc.)

---

## 13. SCHEDULE SUMMARY (bottom of .xlsx)

Include these rows:
- Forecasted Sales (from input)
- Inline Sales (from input)
- Digital Sales (from input)
- Allowed Hours (from input)
- CAP Allowed (from input)
- Inline Sales Allowed (from input)
- Digital Sales Allowed (from input)
- Scheduled Hours (formula: sum of paid hours per day)
- Variance Hours (formula: Scheduled - Allowed)
- Productivity $/Hr (formula: Forecasted Sales / Scheduled Hours)
