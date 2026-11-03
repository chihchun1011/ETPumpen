---
name: lift-heatmap
description: Use when someone sends a gym or workout log (typed sets, or screenshots from a training app), asks for a daily, weekly or monthly training report, asks "what's left to train this week", "which muscles did I skip" or "how many calories did I burn lifting", or wants a muscle heatmap. Recreational, for the ETPumpen workout group; not for medical or physiotherapy questions.
---

# Lift heatmap

Produces a private HTML page: a 3D anatomical muscle model colored by how much of each muscle's weekly target has been trained, estimated calories, and a ranked list of what is left this week. The user prefers visuals over text, so keep chat replies to a few lines.

## Files in this skill

- `assets/template.html`: the page template. Placeholders: `__MODEL_B64__`, `__WEEK_JSON__`, `__MONTH_JSON__`, `__TARGETS_JSON__`.
- `assets/muscles-female.bin`, `assets/muscles-male.bin`: the 3D body, 214 simplified muscle meshes. Not in git; built on first use by `scripts/build_model.py`.
- `scripts/build_model.py`: downloads the BodyParts3D muscle meshes (CC BY-SA 2.1 Japan) and builds the 3D body. Python standard library only.
- `scripts/build_page.py`: fills the template and writes the final HTML.
- `references/model-parts.tsv`: the 214 parts, which muscle key each one counts for, and its triangle budget.
- `references/body-shapes.json`: female and male body proportions (width factor by height).
- `references/exercise-map.md`: which muscles each exercise trains (main = 1 set, helper = 0.5).
- `references/default-targets.json`: starting weekly targets as [min, target, max, note].

## First use: set up the profile

Ask once, in a single short message:
1. Bodyweight and units (kg or lb).
2. Goal: muscle growth, strength, or general fitness.
3. Weekly schedule: which days, and which muscles each day focuses on.
4. Other sports or heavy activities (for example climbing, running) that already load some muscles.
5. Whether they note reps left in reserve (RIR) on each set.
6. Body model: female or male.

Adjust `default-targets.json` to the answers:
- Muscles trained twice a week get the full target. Muscles with little direct work get the lower end.
- Muscles a sport already loads (climbing: lats, mid back, biceps, forearms) get a lower gym target and a higher max.
- Beginners: use the min as the target.

Build the 3D body once for the chosen body model. Ask before running it: it downloads about 560 MB from GitHub into `~/.cache/lift-heatmap/` and takes a few minutes.

`python3 scripts/build_model.py --body female --download` (or `--body male`)

It writes `assets/muscles-<body>.bin`. If the user switches body model later, build the other one the same way; the download is reused.

Measured cost (one CPU core, Python 3, no extra packages):

| Step | Time | Peak memory | Disk |
|---|---|---|---|
| First build, including download | about 2.5 min (about 1 min download, 1.4 min compute) | about 300 MB | 562 MB cache + 1.3 MB model |
| Other body model, cache reused | about 1.3 min | about 300 MB | + 1.3 MB model |
| Daily page (`build_page.py`) | under 0.1 s | about 20 MB | 1.8 MB page |

The cache in `~/.cache/lift-heatmap/` can be deleted once both models are built.

Store the profile and the log somewhere that persists, such as a project document or a file the user keeps. Do not rely on chat memory. Never put the profile in the page, only sets and calories.

## Every time the user sends a log

1. Read the sets from the text or screenshots. Ignore warm-up sets. If reps left is known, count only sets with 3 or fewer reps in reserve. If unknown, count all working sets.
2. Map each exercise to muscles with `references/exercise-map.md`. Main muscle = 1 effective set per set, helper = 0.5.
3. Estimate calories: `kcal = MET x bodyweight_kg x hours`. Use MET 3.5 for normal rest times, 4.5 for short rests or circuits. Hours = first set to last set, plus 5 minutes. The result is an estimate, about 25% either way, and must be labeled that way.
4. Append the day to `week.json` (see format below). Start a new week on Monday.
5. Run `python3 scripts/build_page.py --week week.json --targets targets.json --body <female|male> --month month.json --out page.html`. `--month` is the month so far (see below); leave it out in the first week. If it says the model is missing, build it as in the first-use section.
6. Give the user `page.html` privately: as a private artifact or page if the tool supports one (update the same one on later days instead of creating a new one), otherwise as the file to open in a browser.
7. Reply in at most four lines: calories, the link, the two or three muscles furthest below target, and anything over the max. If something in the log was ambiguous, ask in one line.

## Weekly report (Sunday evening)

Same page, "This week" view. Add one line: muscles at or above 100% of target, muscles under 60%, and one suggestion for next week.

### Setting up the Sunday report (offer once, after the first report)

Weekly reports do not run on their own. After the first daily report, offer in one line to set one up, and let the user pick:

1. **Reminder:** a Sunday-evening reminder (for example 19:00 in the user's time zone) that says "Weekly report: send me today's log or ask for the week view." This works everywhere and needs no stored data.
2. **Scheduled task:** a recurring task that builds the weekly report by itself. Use it only if the environment has scheduling tools. A scheduled run starts without the chat history, so the task prompt must say where `week.json` and the profile are stored, to use this skill, to build the "This week" view, and to send the link plus the one-line summary. If the log is not stored somewhere persistent, use the reminder instead.

Use the real reminder or scheduling tool of the environment, not a note in the chat. If there is none, tell the user to set a weekly alarm themselves and to ask for the week view when it goes off. Confirm in one line what was set and when it fires. Do the same for the monthly report on request (last Sunday of the month).

## Monthly report

The page has a "This month" view whenever `--month` is given. It adds up every session of the month and compares each muscle with its weekly target times the number of weeks in `month.json`, and shows the average sets per week.

1. Build `month.json` from the log: every week whose Monday falls in that month, in order (format below). Partial first or last weeks count as whole weeks, so mid-month the percentages read low until the week is done.
2. During the month, pass the month so far with every daily build, so the user can check the running total at any time.
3. On the last Sunday of the month, build the full month and reply in a few lines: average percent of target per muscle compared with the previous month (from the log), and plan changes. Add sets to muscles that stay under 70%, trim any that go over the max in two or more weeks, and flag muscles never trained.

## week.json format

```json
{
  "label": "2-8 Nov",
  "days": [
    {
      "date": "Mon 2 Nov",
      "kcal": 170,
      "sets": 12,
      "minutes": 65,
      "sets_by_muscle": { "hams": 4, "glutes": 3.5, "quads": 3 }
    }
  ]
}
```

`month.json` is a list of those weeks:

```json
{ "label": "Nov 2026", "weeks": [ { "label": "2-8 Nov", "days": [ ... ] }, { "label": "9-15 Nov", "days": [ ... ] } ] }
```

Muscle keys: quads, hams, glutes, glutemed, adductors, calves, shins, lats, midback, traps, lowback, delt_r, pecs, abs, obliques, delt_f, delt_s, biceps, triceps, forearms.

## Notes

- Percent of target is the main number. Over the max shows purple in the heatmap and means more recovery is needed, not more training.
- Hard-set targets of about 10 to 20 per muscle per week come from general evidence-based guidance, not from medical advice. Keep that framing.
- Credit line required by the model license is already in the page: BodyParts3D, (c) The Database Center for Life Science, CC Attribution-Share Alike 2.1 Japan. Anything built from the model must keep that license.
- The anatomy is a male scan. The male body uses it as is; the female body narrows the shoulders and widens the hips with the width table in `references/body-shapes.json`. If a better freely licensed female muscle model is found, add it to `build_model.py` with the same part keys.

## Never do this

- Never download the BodyParts3D meshes without asking first: about 560 MB.
- Never commit `assets/*.bin` or the download cache. They are built per user, and the binaries are what the repository asked to keep out.
- Never put the profile (bodyweight, goal, schedule) or anything identifying into the page. It holds only dates, sets, minutes and calories.
- Never show calories as exact. Always "about" and plus or minus 25%; it is a MET estimate, not a measurement.
- Never guess a number you cannot read in a screenshot. Ask in one line instead.
- Never count warm-up sets, and never count cardio or sport as sets.
- Never give medical, injury or diet advice. The targets are general training guidance; for pain or injury, say to see a professional.
- Never treat purple (over the max) as "good". It means more recovery, not more training.
