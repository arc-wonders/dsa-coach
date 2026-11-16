# DSA Coach

Daily DSA plan by email, built from your LeetCode history, a curated 189-problem pattern list and spaced repetition.
Web UI for schedule/progress, and a Gemini assistant that edits your schedule ("exams Dec 1–14").

## Setup
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env        # fill in Gmail + Gemini (see below)
.venv/bin/python -m coach init      # loads the list, syncs last 20 solves
.venv/bin/python -m coach import    # optional: full history (needs LeetCode cookies in .env)
.venv/bin/python -m coach serve     # http://localhost:8000, also sends the email daily at DAILY_SEND_TIME
```
Other commands: `sync`, `plan [--force]`, `preview` (writes email_preview.html), `send`, `daily`.

## How planning works (`coach/planner.py`)
- **Effort levels per day**: Off, Light (~15 min, easy only), Steady (~35 min, no Hard), Focused (~60 min, Hard reviews ok),
  Deep (~120 min). Modes (exam/normal/free/off) give the default level; drag points on the Schedule chart to override a day.
  The day before an exam block is automatically Light.
- **Time budget**: each problem has an estimate (new Easy 15 / Medium 30 / Hard 60 min, reviews about half) and the plan fits the day's budget.
- **New problems**: from the 3 earliest patterns under 60% coverage, round-robin, easiest first. List cross-referenced with Striver's SDE Sheet.
- **Reviews**: spaced repetition 3 → 7 → 15 → 30 → 60 days; "couldn't solve" resets to 2 days.
- **Adapting**: missed items carry over; <40% done last week → one level lighter; 3+ missed days → Light restart;
  "Too hard today" swaps a problem for an easier one; "one more" adds a problem.
- **Insights**: goal forecast from your schedule, weekly activity, daily heatmap, per-pattern strength.

## Gmail
Turn on 2-Step Verification, then create an App Password at https://myaccount.google.com/apppasswords.
Put your address and the 16-char password in `.env`.

## Hosting
The email buttons link to `BASE_URL`, so the app must be reachable from your phone and running at send time.
Options: a small always-on VPS / Railway / Render with a persistent disk, or your laptop + Cloudflare Tunnel/Tailscale.
Set `APP_PASSWORD` when exposed to the internet. Without the server running, solves on LeetCode are still
picked up on the next sync; only "couldn't solve"/"no time" clicks need the server.

## Vercel deployment
- `app.py` exposes the FastAPI app; `vercel.json` runs `/api/cron` daily at 01:30 UTC (07:00 IST).
- Storage is Postgres via `DATABASE_URL` (Neon from the Vercel Marketplace). Copy local data with
  `DATABASE_URL=... python -m coach migrate coach.db`.
- Env vars: everything in `.env.example` plus `DATABASE_URL`, `CRON_SECRET`, `APP_PASSWORD`, and `BASE_URL` set to the Vercel URL.
- On Vercel the in-process scheduler is off; LeetCode is synced by the cron and whenever you open the dashboard.
