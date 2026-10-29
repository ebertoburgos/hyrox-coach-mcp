# Running without a coach plan

Use this when `get_coach_plan` returns `has_plan: false` (for example with Apple Health). You plan the
runs as well as the stations. These are common coaching rules of thumb, not formulas. Start conservative.

## Principles
- **Base the plan on what the athlete already does.** Check `get_training_summary(weeks=4)` for runs per
  week and weekly km before proposing anything. Don't jump above their recent volume.
- **Most running stays easy.** Roughly four of every five runs, by time, at a pace where they can speak in
  sentences. Hard running is a small, well-placed share.
- **Only one or two hard run sessions a week.** A hard station class or a compromised run counts as one.
- **Progress slowly:** raise weekly running volume by no more than about 10% from one week to the next, and
  take a lighter week every 3–4 weeks.
- **Let readiness steer.** If the readiness signal or how they feel is poor, swap the quality run for an
  easy one. Don't cram missed sessions into the next days.

## Weekly run structure (starting point)
| Runs/week | Suggested mix |
|---|---|
| 2 | One easy-to-steady run, one longer easy run |
| 3 | One easy run, one quality run (threshold or intervals), one long easy run |
| 4 | Two easy runs, one quality run, one long easy run |

Fit the Hyrox work around them using `training-structure.md`: no leg-heavy station work within 24 h before
the quality or long run, and one compromised-run session a week while building. The compromised run can be
the quality run on some weeks instead of an extra session.

## Session types
- **Easy / base:** conversational pace, 30–50 minutes. Use time, not distance.
- **Long easy run:** the longest run of the week, same easy effort. Build toward comfortably running
  8–10 km, since the race is 8 km of running on tired legs.
- **Threshold:** for example 3 × 5 minutes at "comfortably hard" effort, 2 minutes easy jog between. If the
  source supplies a threshold pace or HR, use it; otherwise use effort ("could say a few words").
- **Intervals:** for example 6 × 2 minutes hard but repeatable, 2 minutes easy between. Only for athletes
  already running comfortably, and not in the same week as a hard simulation.
- **Compromised run:** see `training-structure.md`.

## Targets
Use the athlete's own data to set targets:
- **Easy:** effort by feel, or heart rate if they know their zones.
- **Quality:** a pace range from recent runs, or the threshold anchor if available.
- **When unsure:** use RPE (easy about 3–4 of 10, threshold about 6–7, intervals about 8) and adjust after
  seeing how it went.

## First-time or return-to-running athletes
- Build running frequency before pace. Walk-run is fine.
- Hard running only after several weeks of consistent easy running.
- Pain that changes the way they run, or lasts beyond the session: stop and advise a physio or doctor.

## Keeping the plan alive
There is no plan tool, so state the week's plan clearly in each weekly review, and restate it when asked
"what's next". After each run, compare what they did with the plan using `list_sessions`, and adapt.
Save notable context (a niggle, a missed week, a change of goal) with `log_session_note`.

## Taper without a plan
For the last 7–10 days, cut running volume by roughly a third to a half. Keep one or two short efforts
at race effort, with full recovery, so legs stay sharp. No new long runs or hard sessions.
