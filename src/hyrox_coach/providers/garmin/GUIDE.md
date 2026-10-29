# Garmin Connect: coaching guide

Status: available. Data comes from the athlete's Garmin Connect account via an unofficial login.

## What it supplies
Activities, sleep, HRV, resting HR and Body Battery, Garmin's own training readiness, training load and
load balance, the Garmin Coach running plan, and fitness trends (VO2 max, race predictions, endurance
score, hill score, lactate threshold, running impact vs tolerance). It does **not** supply station-level
data from classes: a HIIT or cardio session arrives as one block with heart rate only.

## Reading the data
- **Training readiness (0–100):** levels run from Poor (lowest) through Low, Moderate and High to Prime.
  Garmin lists what limits it (sleep, recovery time, HRV, acute load, stress and sleep history). Quote the
  limiting factors, not just the score. Low readiness after a hard class is normal; low for several days is not.
- **HRV status:** compares the recent weekly average with the athlete's personal baseline range
  (balanced low to balanced upper). Judge the trend, and only against their own range.
- **Body Battery (0–100):** an estimate of energy reserve. A low morning peak after a full night means
  poor recovery; a normal peak that drains fast is a training or stress signal.
- **Training effect (aerobic, anaerobic; 0–5):** an anaerobic effect of about 2 or more means the session had
  real hard efforts. Use it with the load number to judge how hard a session was.
- **Load, acute:chronic ratio and load balance:** Garmin labels the ratio (for example OPTIMAL) and shows
  four-week load against target ranges for aerobic low, aerobic high and anaerobic. Quote Garmin's label.
  Hyrox-style classes mostly feed the anaerobic and high-aerobic buckets, so those can run full while
  aerobic low is short: the usual fix is more easy running.
- **Endurance score:** classes (for example intermediate, trained, well trained, expert) come with Garmin's
  thresholds. The tools report how much running vs HIIT contributes, which shows if classes are carrying
  the score.
- **Hill score:** strength plus endurance on climbs. Minor for a flat race; don't chase it.
- **Race predictions (5k to marathon):** estimates of road-running fitness from VO2 max and training. They
  are not Hyrox times. Use the trend, not the absolute numbers.
- **Lactate threshold (HR and pace) and running power:** updated by hard guided runs. Useful anchors for
  threshold pacing; if stale, say so.
- **Running impact vs tolerance:** weekly impact load as a percentage of Garmin's tolerance. A rising
  percentage with sore legs is a cue to hold volume.
- **Garmin Coach plan:** an adaptive plan of Base, Long Run, Threshold and VO2 Max sessions with HR or pace
  targets and rest days. Key workouts are flagged. It adapts to what the athlete completes. The coach owns
  the runs: you can read the plan but not edit it. To change the plan, the athlete uses Garmin Connect.

## Traps
- **Class load is estimated from heart rate.** Heavy, low-heart-rate work (sleds, carries, lunges) is
  underrepresented, so a brutal station day can look moderate. Weigh the athlete's own account of the
  session over the number.
- **A class is one lap.** There are no station splits or run-after-station splits unless the athlete used lap
  presses or a structured workout.
- **Readiness can be stale or missing early in the day** if the watch has not synced. If today's data is
  empty, ask the athlete to sync the watch to Garmin Connect, then try again.
- **Treadmill and indoor pace is less reliable** than outdoor GPS pace. Prefer HR and effort for indoor runs.
- **Race predictions look flattering after good weeks and harsh after bad ones.** Don't over-read a few days.
- **Cached data:** today's numbers are cached for about half an hour, past days for a day.

## Recording sessions
- Garmin has no built-in Hyrox activity profile on its watches as of late 2026 (check your model). Common
  workarounds: a Cardio or HIIT activity with a lap press at every run and station change, a multisport
  activity of Run + Cardio legs, a custom structured workout, or a Connect IQ app built for hybrid racing.
- **Simulations:** press lap at every change. That gives usable run and station splits.
- **Classes:** one HIIT activity is fine. Capture the details afterwards in `log_session_note`.
- Wear the watch snug for accurate heart rate during sleds and carries; wrist HR can lag or spike on
  gripping and impact.

## Setup and troubleshooting
- Login happens once in the athlete's own terminal with `hyrox-coach login` (credentials and any MFA code
  are typed there, never in the chat). Tokens are stored locally.
- `hyrox-coach doctor` shows which metrics the athlete's watch and account provide.
- A login problem or rate limit (HTTP 429): wait and try later; don't retry in a loop.
- This uses an unofficial library that can break when Garmin changes its login. If tools suddenly fail for
  everyone, say so and point to the project's issues page.
- Never ask the athlete to paste a password or token into the chat.
