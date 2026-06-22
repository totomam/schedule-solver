# Paddock Schedule Rules

Complete reference for building the weekly schedule. Given availability sheet, request-off book, and sales forecast — apply these rules to produce the schedule.

**Solver source (GitHub):** `https://raw.githubusercontent.com/totomam/schedule-solver/main/solver2.py`
At the start of each session, `web_fetch` this URL to get the latest solver code before building or editing anything. If the branch changes, update this URL.

---

## 1. INPUTS NEEDED EACH WEEK

1. **Availability sheet** (PDF/text listing each employee's avail per day)
2. **Request-off book** (notebook page with names handwritten under each day of the week)
3. **Sales forecast** with allowed hours per day (Forecasted Sales, Inline, Digital, Allowed Hours, CAP Allowed, Inline Sales Allowed, Digital Sales Allowed)

---

## 2. HOURS RULES

### Manager hours (set defaults — only override when explicitly needed)
- **John Martin (Jay)**: Off Tuesday AND Wednesday normally. Default Mon 6a-3p, Thu/Fri/Sat 10a-8p, Sun 11a-5p.
- **Myles Palmer**: Mon 11a-8p, Thu 11a-8p, Fri 12p-9p, Sat 12p-9p, Sun 11a-8p = 45h. Off Tue/Wed. (11-8 on weekdays + Sunday; 12-9 Friday & Saturday.)

### Non-manager hour caps
- **Maximum 40h** for everyone except Jay and Myles (NO OVERTIME — we don't pay it)
- **Minimum shift length: 4 hours**
- **Part-time shifts capped at 8 hours per shift.** Only full-time, shift leaders, managers, and the blanket-approved 10h people (see below) may be scheduled longer than 8h. If a PT shift over 8h is genuinely needed, get manager permission first and log it as a one-time exception.
- **10-hour-OK people** (may work up to 10h without asking): all leaders/managers, plus Adam, Mason, Michael, Molly, Noah Hiner, Ava, Remi, Izzy, Zac. Other PTs need explicit one-time manager approval for anything over 8h.
- **Maximum 5 days per week for everyone.** Nobody is scheduled more than 5 days.

### Paid vs unpaid breaks
- **Paid breaks (no deduction)** — these people get hours as-is:
  - Managers ONLY: John Martin (Jay), Myles Palmer
- **Everyone else, INCLUDING the 5 shift leaders** (Bowen Benedict, James Baker, Trinity Stringer, Gobi Weathers, Mary Dean): subtract 0.5h from any shift ≥ 5 hours. The shift leaders clock out for a 30-min unpaid break like all hourly staff.
  - Example: 8a-4p (8h raw) shows as 7.5 paid
  - Example: 4:30p-9p (4.5h raw) shows as 4.5 paid (under 5h = no deduction)
- Per-person cells in the .xlsx show FULL (raw) hours; the bottom "Scheduled Hours (paid)" row shows paid totals after break deductions. This paid model is the correct basis for planning.

### FT target hours
- Shift leaders (Bowen, James, Trinity, Gobi, Mary): **39–40h range**. Gobi is capped at ~37h raw by her fixed schedule and the 12h close-then-open rule — she's the exception.
- Other FT + college kids (Zac): **35–40h range**

---

## 3. SCHEDULING CONSTRAINTS

### Jay-specific (default set schedule)
- **Off Tuesday AND Wednesday** normally
- **Mon 6a-3p** (9h) — admin time at open, doesn't count as opener
- **Thu/Fri/Sat 10a-8p** (10h)
- **Sun 11a-5p** (6h)
- **Never works past 9pm** unless absolute emergency close
- **Never schedule a 9a-9p (12h) shift** — too long
- Override default only when you explicitly need to (e.g., a one-off week covering 6 days)

### Myles-specific (default set schedule)
- **Mon, Thu 11a-8p** (9h each)
- **Sun 11a-8p** (9h)
- **Fri, Sat 12p-9p** (9h each)
- **Off Tue, Wed**
- Default total: 45h (11-8 on weekdays + Sunday; 12-9 Friday & Saturday)
- **Never works past 9pm** unless emergency close
- Override default only when explicitly needed (e.g., emergency close)

### Close-then-open rule
- **Minimum 12 hours between close and next-day open**
- Example: 11pm close → 11am next day open = ✓ (12h gap)
- Example: 11pm close → 10am next day open = ❌ (only 11h)

### Leader coverage
- **Every day MUST have a shift leader or manager opening AND closing**
- Opening = working at or before 10am
- Closing = working until 10pm or later
- Leaders/managers available to anchor open & close: Jay, Bowen, James, Trinity, Gobi, Mary. Plan leader coverage around each leader's days off and any request-offs that week.
- If no leader is available to close on a given day (rare): Myles can close as an emergency exception.

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
- **Target (not counting Jay): 6 openers every day, Monday through Sunday.**
- A day may run one under if the bodies genuinely aren't available (weekend availability is the usual bottleneck).
- **Stagger opener start times to lower labor when possible.** Don't start everyone at 9:00 — only the open truly needs a couple of bodies at the door. Have **2 people start at 9:00** and stagger the rest across **9:15, 9:30, 9:45, 10:00**. This trims paid hours off the slow early-morning window while still ramping coverage into the lunch build. Only bunch multiple people at 9:00 when the day genuinely needs the early hands (e.g. heavy prep or a big forecast).

### Lunch (people working at noon)
- **Default target: 9 lunch every day if possible**
- 8 is only acceptable in emergencies or on days with very low projected sales
- Higher (10+) for days with higher forecasted sales (e.g., Sat target 10)

### Closers (people working past 10:30pm — i.e., to 11pm close)
- **Hard target: exactly 5 closers per day, 6 on Friday, Saturday, and Sunday.** Do not run more than the target — too many closers was a recurring problem. Treat this as a firm number, not a "minimum."
- **Never have more than one of Gobi, James, or Trinity closing on the same day.** If Gobi or Trinity is closing, move James to a mid or open shift (he does not close that day). At most one of the three closes per day.

### Evening staffing floor (every day)
- **9pm: at least 7 people still working past 9:00pm Mon–Thu and Sun.**
- **Friday & Saturday: hold the past-9pm count at exactly 8** — floor of 8, but capped at 8. To keep it from ballooning (the heavy Fri/Sat dinner crew would otherwise leave ~10 people on past 9), push the surplus dinner-crew shifts to **end at exactly 9:00pm**, since a 9:00 end does not count as "past 9pm." This raises the effective evening floor to 8 while trimming late-evening labor.
- **9:30pm: at least 6 people working past 9:30pm Monday–Thursday; at least 7 Friday–Sunday.**
- Counting follows the standard convention: a person counts toward a time only if they're working *past* it (a shift ending exactly at 9:00pm does not count toward the 9pm floor).
- This is broader than the closer count (closers work to 10:30/11pm); it keeps enough hands on the floor through the back half of the dinner rush before close.

### Dinner (people working past 5pm)
- Depends on day/forecasted sales (see table below)

### Lunch/Dinner targets by day
*(may shift week-to-week based on forecasted sales — these are the current working targets)*

| Day | Lunch / Dinner |
|-----|---------------|
| Monday | 9 / 10 |
| Tuesday | 9 / 10 |
| Wednesday | 9 / 10 |
| Thursday | 9 / 11 |
| Friday | 10 / 14 |
| Saturday | 10 / 13 |
| Sunday | 11 / 12 |

Higher forecasted sales → higher targets. Use lunch/dinner targets as your primary coverage check. Closers run exactly 5/day (6 on Friday & Saturday) — see Closers section.

---

## 6. VARIANCE TARGETS (paid hours over allowed hours)

| Day | Variance Target |
|-----|-----------------|
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

### Strong PT (give more hours, 18-25h+ target)
- Cai Cotton
- Tiffany Huffman
- Izzy Simpson
- Kara Thompson
- Nathan Paasewe
- Reese Bezehertny
- Lorelei Regan
- Gracelyn Dailey — **availability changes every month and is NOT in the standard availability sheet. She prints and brings her own calendar. Always verify her current availability before each build; do NOT assume she's "any"/open.** (Example: for 6/22-6/28 she was available Saturday only.)

### Weak / limited group — "don't pull their weight," spread out, prefer one day each
- **Full group (all five): Layton Angermeier, Emily Owens, Brian Carver, Bryan Bishop, Jason Britt**
- **Prefer-one-day rule (applies to ALL FIVE):** schedule each of them just one day/shift per week when possible. Only give a second day if coverage genuinely requires it.
- **One-per-meal-period rule (applies ONLY to Brian Carver, Bryan Bishop, Jason Britt):** never more than ONE of these three working the same meal period (lunch or dinner) on any given day. Lunch = on the floor at noon; dinner = working past 5pm. Each lunch and each dinner across the week may contain at most one of them. (One-per-meal exceptions can be approved individually.)
- Spread them across the week rather than clustering. Prefer stronger people on the busy days (Fri/Sat/Sun) and use these five to fill genuine gaps.

### Middle PT (use as needed for coverage, ~10-15h)
- Shayden Howard, John Dugan, Kayden Anderson, Peyton Shaw, Amiyah Bartley, Logan Frias, Richard Raglin, Oliver Croasdaile, Harper Flynn
- **Ryder**: new hire, available any day/time, PT standard (max 8h shifts, takes break, max 5 days per week)

### New / occasional
- **Jacob Cothern**: PT, 2 shifts only, available Mon-Thu 5p-9:30p (dinner shifts). Place on the higher-volume of his available days.
- **Zac Duffy**: college kid (CK), wants 30+h, treated FT-ish — cleared for 10h shifts. **Target him at 28+ hours** (give him real hours, not a couple of short shifts). Available Mon/Tue/Thu/Sun.

### Leaving / on way out
- Get 1-2 shifts max, no need to prioritize hours

### Special cases
- **Sienna Underwood**: no availability listed, generally skip
- **Hayden Roush**: depending on week — may request off entirely
- **Sandya Wright**: weekdays-only normally (school); summer break may change

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
- The only people scheduled before 9am: **Jay** (Mon 6a), **Bowen** (8a Mon-Fri), **Gobi** (Saturday open), **James** (Sunday 8a). No one else.

### Morning starts
- Don't have everyone start at 9am — stagger the openers. At most 2 people start at exactly 9:00 (plus Bowen's 8a anchor); stagger the rest at 9:15a, 9:30a, 9:45a, 10a.
- At least one prep person (Michael, Tiffany, Noah, Gracelyn, Molly; Reilly = dough on Sunday) should be among the 9:00 starters.
- Bowen anchors morning at 8a (set schedule)

### Afternoon transitions
- 3p-5p transition window: stagger so coverage doesn't spike
- Use 3p, 3:30p, 4p, 4:30p, 5p, 5:30p starts

### Openers — cap (not counting Jay)
- An opener is anyone who starts work at or before 10:00am. **Jay never counts toward the opener total on any day.**
- Target is 6 openers every day (not counting Jay). Don't exceed the target for the day.
- If a day is running over, push the extra early-starters to an 11am start — they still cover lunch and dinner, they're just no longer openers.

### Afternoon headcount (2pm / 3pm / 4pm) — HARD TARGETS
- **These are hard targets to hit exactly, not a guide:**
  - **Normal days (Mon–Thu): 2pm = 8, 3pm = 6, 4pm = 5**
  - **Friday: 2pm = 8, 3pm = 7, 4pm = 6**
  - **Saturday: 2pm = 9, 3pm = 8, 4pm = 7**
  - **Sunday: 2pm = 11, 3pm = 8, 4pm = 6**
- **Counting convention (applies to ALL headcount counts at every clock time):** a person counts toward the headcount at time T only if they are still working *past* T. If their shift ends exactly at T, they do NOT count toward T — they're considered gone. (Floor at T = shifts with start ≤ T AND end > T.) So someone ending at exactly 3:00 counts at 2pm but not 3pm.
- Build the afternoon to land on these numbers. The 3-5pm peak ceiling still applies (≤8 normal/Fri/Sat; Sunday's 2pm/3pm run higher by design).
- Mechanics for hitting them cleanly: extend or trim daytime (lunch) shifts to control the 2pm and 3pm counts; stagger when the dinner crew starts (3/4/5pm) to control 3pm and 4pm; this also lets you push saved afternoon hours into dinner and weekend coverage.

### Departure timing
- **No one leaves before 2pm** on any day — this is a hard rule with no exceptions. The earliest any non-Sunday shift may end is 2:00pm.
- **At most 2 people leave at 2:00pm or 2:30pm on any given day.** Don't bunch departures — spread the early-out shifts so no more than two end in that 2:00/2:30 window.
- **Sunday: no one leaves before 3pm.** The earliest any Sunday shift may end is 3:00pm. To make the Sunday afternoon drop (11 → 9), send exactly 2 people home *at* 3:00 (they end at 3:00, so they count at 2pm but not 3pm).
- Forbidden end times: **no shift may end strictly between 5:00pm and 8:00pm** (5:00pm and 8:00pm themselves are fine; ends at 5:15, 5:30, … 7:45 are banned) — unless a shift is specifically pinned otherwise. Also none before 2:00pm (3:00pm Sunday).
- **Evening-departure stagger:** no one ends at 8:15pm or 8:45pm (banned). At most **2 people end at 8:00pm** and **2 at 8:30pm** — except Friday & Saturday, where at most **1 ends at 8:00pm**. (Managers/leaders on fixed shifts are exempt from these counts; the caps govern the flexible staff the solver places.)

### Shift end times — NEVER end at 6pm or 7pm
- **Do not schedule anyone to leave between 5:00pm and 8:00pm** (exclusive) — that's the dinner ramp and rush. A shift should either end at **5:00pm or earlier** (a lunch/midday body, off before dinner ramps) OR **8:00pm or later** (a dinner body that works through the rush). The only exception is a shift specifically pinned to end in that window.
- When shortening a dinner shift to save hours, pull it back to 5pm; when extending a midday shift, push it to 8pm+

### Evening closes
- **Closer end-time distribution (target for each day):**
  - 2 people until 11:00pm
  - 2 people until 10:30pm
  - 1 person until 10:15pm
  - 1 person until 10:45pm
- On 5-closer days (Mon–Thu, Sun) the solver will naturally drop one slot (typically 10:45pm).
- **Adam always ends at 10:45pm or 11:00pm** (set pattern, Mon-Fri). Enforced in solver gen().
- **All 5 shift leaders (Bowen, James, Trinity, Gobi, Mary): if on a closing shift (end ≥ 10pm), must go to 11pm** — leaders are in charge and stay until close. Enforced in solver gen().
- Mary: solver places her freely Mon–Fri; **Saturday only** is pinned as a 3–11pm close.
- **Late-arrival caps: at most 1 person may start at each of 5:15pm, 5:30pm, 5:45pm, and 6:00pm** (one per slot, four separate caps). Don't stack late dinner starts — spread evening arrivals across earlier start times.

---

## 10. FT WEEKLY STRUCTURE (defaults)

### Set schedules (don't change without reason)
- **Bowen**: Mon-Fri 8a-4p — **always a full 8a-4p, every day he works. Never short his hours** (don't trim him to 8-3, etc.)
- **Adam**: Mon-Fri, **always ends at 11pm** (e.g. 4p-11p, or starts earlier when more hours are needed). Adam never ends before 11pm.
- **Mary**: Sat 3p-11p (pinned); other days solver-placed within her 3p-11p avail window
- **James**: any most days, Wed 3-11, Sun 8-4. **Does not close on any day Gobi or Trinity closes** (move him to mid/open that day).
- **Trinity**: rotates between AM and PM days; usually Mon 9-4, Tue 2-11, Wed any, Thu any, Fri 5-11, Sat 9-4, Sun off
- **Gobi**: Mon 4-11, Wed 9-5, Sat 9-5, Sun 3-11. **Tuesday opens at 11a (not 10a)** — opening earlier would break the 12-hour rule after her Monday 11pm close.
- **Michael**: M-F 9-5 (limited by 2nd job — sometimes ~3 days)
- **Molly**: any/prefers days. **Never works past 5pm** — every Molly shift ends at 5:00pm or earlier.
- **Noah**: M-F 9-5 area, often using 9:15 start trick
- **Ava**: any, prefers mornings (FT)
- **Mason**: any 10-10, varied shifts
- **Reilly**: max 3 shifts, prefers 9-5
- **Remi (kitchen)**: 9a-11p avail M/T/Th/F/Sat. Works afternoon/evening prep shifts (3p-11p typical), NOT late-night close

---

## 11. PROCESS CHECKLIST (in order)

When building a new schedule:

1. **Lock in mandatory hours**:
   - Jay = off Tue & Wed normally (Mon 6-3, Thu/Fri/Sat 10-8, Sun 11-5)
   - Myles = default 45h (Mon/Thu/Sun 11-8, Fri/Sat 12-9, off Tue/Wed)
   - Shift leaders aim for 40h (Bowen, James, Trinity, Gobi, Mary)

2. **Add FT regulars** at their set patterns (Bowen, Adam, Mary, Michael, etc.)

3. **Add strong PT** with 18-25h each, spread across days

4. **Fill coverage gaps** using middle PT

5. **Apply the weak/limited group** (Layton, Emily, Brian, Bryan, Jason) — one shift each where possible; keep Brian/Bryan/Jason to one per meal period

6. **Validate**:
   - [ ] All request-offs honored (cross-check against book line-by-line)
   - [ ] All shifts within each person's availability (cross-check avail sheet; verify Gracelyn's monthly calendar)
   - [ ] Every day has leader open AND close
   - [ ] At most ONE of Gobi/James/Trinity closes per day
   - [ ] No close-then-open under 12h (incl. leaders — Gobi opens Tue at 11a)
   - [ ] No hourly over 40h; Adam exactly 40 and always ends 11pm; FT non-leaders 35-40; Zac 28+
   - [ ] No one starts before 9am except Jay/Bowen/Gobi(Sat)/James(Sun)
   - [ ] No one leaves before 2pm; Sunday no one leaves before 3pm
   - [ ] ≤2 people leave at 2:00/2:30pm; ≤2 people start at 5:30/6:00pm
   - [ ] Molly never past 5pm
   - [ ] 2/3/4pm hard targets hit exactly (Mon-Thu 8/6/5; Fri 8/7/6; Sat 9/8/7; Sun 11/8/6)
   - [ ] Lunch hits day-target, dinner hits day-target
   - [ ] Openers (Jay never counts): 6 every day. Closers exactly 5/day (6 Fri-Sat-Sun)
   - [ ] Every available person gets at least one shift
   - [ ] Weekly total variance lands in the +25 to +30 range (paid hours over allowed)
   - [ ] No shift under 4h

7. **Build the .xlsx** in reference format (employee rows alphabetical, with Schedule Summary at bottom)

---

## 12. ALPHABETICAL NAME MAP (printed schedule vs. nicknames)

| Printed | Goes by |
|---------|---------|
| John Martin | Jay |
| Claire Cotton | Cai |
| Danielle Sullinger | Remi |
| Kyle Summers | Molly |
| Lucas Baker | James |
| Noah Weathers | Gobi |
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
