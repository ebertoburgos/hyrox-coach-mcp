# Apple Health (Apple Watch): coaching guide

Status: planned. The Apple Health provider is not implemented yet. This guide describes how the coach
should behave once it ships, so the behaviour is settled before the code.

## What it supplies
From the Health app's export (or an optional automatic export app): workouts with duration, energy and
heart rate; heart-rate samples; resting heart rate; heart rate variability; sleep stages; VO2 max
estimates; and routes for outdoor workouts. Workout segments or markers are included when the athlete
recorded them. It does **not** supply: a readiness score, training load, a running coach plan, race
predictions, an endurance score, or lactate threshold. This tool estimates readiness and load instead.

## Reading the data
- **HRV is SDNN, not Garmin's or Whoop's measure.** Apple samples it intermittently, so single values are
  noisy. Use a multi-day average and compare only against the athlete's own baseline. Never compare it to
  numbers from another brand.
- **Resting heart rate:** a rise of about 5 bpm or more above the athlete's usual, for several days, is a
  better fatigue signal than any single HRV reading.
- **Sleep:** use duration and stage totals. Consistency across the week matters more than one night.
- **Readiness here is an estimate** from HRV vs the athlete's baseline, resting HR trend, sleep and recent
  load. It is labelled as estimated. Hold it with less confidence than a provider's own score, and lean
  more on how the athlete says they feel (energy, soreness, mood).
- **Training load is an estimate** from workout duration and heart rate. Treat it as rough.
- **VO2 max:** the watch typically updates it from outdoor walks, runs and hikes. Treat it as a slow trend,
  not a daily number.
- **No coach plan:** use the "running without a plan" guide. You plan the runs as well as the stations.

## Traps
- **Data is as fresh as the last export.** Ask when the athlete last exported or synced. If it is older
  than a few days, say the recommendations are based on older data and suggest a fresh export.
- **HRV and heart-rate numbers are not comparable across brands or devices.** If the athlete changed watch,
  restart the baseline instead of reading a jump as fitness or fatigue.
- **Workout type choice changes the data.** A class recorded as the wrong type may be read as a run or
  strength session. Check what it was before drawing conclusions.
- **A class is usually one block** unless the athlete recorded segments or used a structured workout.
- **Large exports:** the first import can take a while. This is normal.
- **Sensitive data:** an Apple Health export holds far more than training data. It stays on the athlete's
  machine. Don't ask them to paste or upload it into a chat.

## Recording sessions
- Use the Workout app and pick the type closest to the session: Running for runs, and the type that fits
  a class (for example HIIT, Cross Training or Functional Strength, depending on the watch). There is no need
  to rely on a dedicated Hyrox type.
- For simulations, mark a segment at every run and station change if the watch supports it (the Action
  button or a tap, depending on the model). That gives usable splits. Check what the watch offers.
- Capture class details in `log_session_note` afterwards: the watch can't see weights or reps.
- Make sure the watch is snug for heart rate accuracy during sleds and carries.

## Setup and troubleshooting
- No login. The athlete exports from the Health app (profile picture, then "Export All Health Data"), and
  points the tool at the exported file or folder. An automatic export app can drop fresh files into a folder.
- `hyrox-coach doctor` will show which data types were found in the export.
- If a metric is missing, check that the watch recorded it and that the export includes it.
- Never ask the athlete to send the export through the chat.
