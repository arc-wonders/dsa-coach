"""python -m coach <command>

init           create DB, load curated list (fetches titles from LeetCode), set goal
import         full history import (needs LEETCODE_SESSION + LEETCODE_CSRFTOKEN in .env)
sync           pull your last 20 accepted submissions (public, no cookie)
plan [--force] build/show today's plan
preview        write today's email to email_preview.html
send           email today's plan now
daily          sync + plan + email (what cron / the scheduler runs)
serve          start the web app (also runs the daily scheduler)
migrate PATH   copy a local SQLite DB into DATABASE_URL (Postgres)
"""

import json
import sys
from datetime import timedelta

from . import config, db, jobs, mailer, planner, tracker


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "init":
        db.init_schema()
        print("Loading curated list and fetching titles from LeetCode (~1 min)...")
        missing = tracker.seed_problems()
        if missing:
            print("Slugs LeetCode didn't recognise:", missing)
        with db.tx() as c:
            total = c.execute("SELECT COUNT(*) FROM problems WHERE in_list=1").fetchone()[0]
            if not db.get_setting("goal_total", c):
                db.set_setting("goal_total", total, c)
            if not db.get_setting("goal_end", c):
                db.set_setting("goal_end", (db.today() + timedelta(days=140)).isoformat(), c)
        print(f"{total} problems loaded. Goal: {db.get_setting('goal_total')} by {db.get_setting('goal_end')}")
        print("Seeding from recent submissions...", tracker.sync_recent(), "found")
    elif cmd == "import":
        print(json.dumps(tracker.full_import(), indent=2))
    elif cmd == "sync":
        print(tracker.sync_recent(), "new solve(s)")
    elif cmd == "plan":
        p = planner.generate_plan(force="--force" in sys.argv)
        print(f"{p['day']} · {p['mode']} · {p['note'] or ''}")
        for i in p["items"]:
            print(f"  [{i['kind']:6}] {i['title']} ({i['difficulty']}, {i['pattern']}) - {i['reason']} [{i['status']}]")
    elif cmd == "preview":
        _, _, html = mailer.render(planner.generate_plan())
        out = config.ROOT / "email_preview.html"
        out.write_text(html)
        print("wrote", out)
    elif cmd == "send":
        print("sent" if mailer.send_plan(planner.generate_plan()) else "nothing to send today")
    elif cmd == "daily":
        print(jobs.daily_run())
    elif cmd == "migrate":
        print(db.copy_from_sqlite(sys.argv[2]))
    elif cmd == "serve":
        import uvicorn
        uvicorn.run("coach.web:app", host="0.0.0.0", port=int(config.env("PORT", "8000")))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
