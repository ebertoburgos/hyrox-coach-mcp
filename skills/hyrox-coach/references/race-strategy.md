# Race strategy, race week, race morning, post-race

Guidance, not guarantees. Build it from the athlete's own numbers and a simulation, and give ranges.
Typical finish times and splits vary a lot by division and venue; don't present benchmark times as facts.

## Building a pacing plan
Inputs: `get_progress` (predicted 5k/10k, lactate threshold pace), recent 1 km paces from
`list_sessions`, logged station times at race weights, division weights from `get_race_profile`.

1. **Run pace.** Start from the athlete's comfortable steady 1 km pace, not their 5k or 10k race pace.
   Plan the early runs at or just under that effort. Athletes commonly slow 10–20% across the eight runs;
   aim to keep the fade under about 10% by starting controlled. Confirm with a simulation.
2. **Station pace.** Plan each station at an effort you can recover from while running next, not the
   fastest you can do it. Expect sled push and wall balls to be the highest-cost stations for many people
   (heavy legs and high heart rate); say so only if their logs support it.
3. **Transitions (Roxzone).** The walk or jog between run and station and back is part of the total time
   and the recovery. Move with purpose, but don't sprint it. Know where each station is and how you enter it.
4. **A, B, C goals.** A: the ambitious time. B: the realistic one. C: finish with even pacing and no
   injury. For a first race, B and C are the main goals.
5. Write the plan as a short table: run 1–8 target pace and effort, each station's strategy, and the one
   cue per segment ("run 1: easy, hold back", "wall balls: sets of ...").

## Pacing rules that hold up
- **Runs 1–2: controlled.** The adrenaline makes them feel easy, which is the trap.
- **Runs 3–6: even.** This is where pace discipline wins time.
- **Runs 7–8: spend what is left.** Only the last run is for racing.
- If heart rate spikes much higher than in training at the same effort, ease off for a minute rather than
  fading later.

## Station tactics
See `stations.md` for cues. In race plans, add:
- Wall balls: decide the set structure in advance (for example, equal sets with a planned short break).
  Break before failure, not after.
- Farmers carry: pick up and walk fast; if a pause is necessary, take it early and short and check what is
  allowed.
- Sled work: stay low and keep the steps short and constant; don't stand up to rest.
- No-reps cost more than a controlled rep. Know the standards.

## Race week (final 7 days)
- Keep the coach-plan taper. Add one short station touch-up early in the week at race weights, and
  nothing new.
- Sleep is the training. Aim for consistent hours; one bad night before race day matters less than the week.
- Fuel normally, with a bit more carbohydrate in the last 2 days. Hydrate steadily; don't overdo it.
- Gear: shoes already worn in (grip for sleds), anything that chafes is tested, plan for a warm hall.
- Logistics: registration, start time and heat, parking or transport, what to carry, who is waiting for you.
- Check the rulebook once more for movement standards and the division's weights.

## Race morning
- Wake with time to eat 2–3 h before the start; foods the athlete has used in training.
- Arrive early. Short warm-up: easy jogging, mobility for hips and shoulders, a few practice reps (sled stance,
  wall ball squats, SkiErg pulls). Don't tire yourself.
- First 1 km run: the plan says controlled. Say it again.
- Drink and fuel as practised. Nothing new.
- If you feel awful in the first three runs, slow down; races are lost by fading more than by starting easy.

## Post-race debrief
1. Ask for official splits per run and station, how it felt, and anything that went wrong (no-reps,
   grip, stomach, cramp, pacing).
2. Compare to the plan: fade across runs, station costs, transitions. Log with `log_session_note`
   (stations with `time_s`; run splits in `text`).
3. Give the biggest time lever and one change for the next training block.
4. Recovery: a few easy days, then rebuild gradually. Ask about the next goal before suggesting more load.
