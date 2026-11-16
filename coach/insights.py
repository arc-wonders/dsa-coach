"""Trend data for the Insights page and charts."""

from collections import defaultdict
from datetime import date, timedelta

from . import db, planner


def _events(conn) -> list[dict]:
    """Attempts classified as new (first solve), review (later solve) or failed."""
    rows = conn.execute(
        """SELECT a.slug, a.ts, a.outcome, p.in_list, p.difficulty FROM attempts a
           JOIN problems p ON p.slug=a.slug ORDER BY a.ts"""
    ).fetchall()
    last_solve: dict[str, int] = {}
    out = []
    for r in rows:
        if r["outcome"] == "failed":
            kind = "failed"
        elif r["slug"] not in last_solve:
            kind = "new"
        elif r["ts"] - last_solve[r["slug"]] < 43200:
            continue  # same solve recorded twice (email click + LeetCode sync)
        else:
            kind = "review"
        if r["outcome"] == "solved":
            last_solve[r["slug"]] = r["ts"]
        out.append({"slug": r["slug"], "day": db.ts_to_date(r["ts"]), "kind": kind,
                    "in_list": r["in_list"], "difficulty": r["difficulty"]})
    return out


def _start_date(conn) -> date:
    s = db.get_setting("start_date", conn)
    if not s:
        row = conn.execute("SELECT MIN(day) FROM plans").fetchone()
        s = row[0] if row and row[0] else db.today().isoformat()
        db.set_setting("start_date", s, conn)
    return date.fromisoformat(s)


def build() -> dict:
    with db.tx() as c:
        today = db.today()
        events = _events(c)
        pace = planner.pace(c)
        start = _start_date(c)
        goal_end = date.fromisoformat(pace["goal_end"])

        # ---- weekly (last 12 weeks, Monday-based) ----
        this_monday = today - timedelta(days=today.weekday())
        weeks = [this_monday - timedelta(weeks=i) for i in range(11, -1, -1)]
        wk = {w: {"new": 0, "review": 0, "failed": 0, "planned": 0, "done": 0} for w in weeks}
        for e in events:
            w = e["day"] - timedelta(days=e["day"].weekday())
            if w in wk:
                wk[w][e["kind"]] += 1
        for r in c.execute("SELECT day, status FROM plan_items WHERE day>=? AND status!='swapped'",
                           (weeks[0].isoformat(),)):
            d = date.fromisoformat(r["day"])
            w = d - timedelta(days=d.weekday())
            if w in wk and d <= today:
                wk[w]["planned"] += 1
                wk[w]["done"] += r["status"] in ("solved", "failed")
        weekly = [{"week": w.isoformat(), "label": w.strftime("%d %b"), **wk[w]} for w in weeks]

        # ---- daily heatmap (last 26 weeks) ----
        first = this_monday - timedelta(weeks=25)
        per_day: dict[date, set] = defaultdict(set)
        for e in events:
            if e["kind"] != "failed" and e["day"] >= first:
                per_day[e["day"]].add(e["slug"])
        heat = []
        d = first
        while d <= today:
            heat.append({"day": d.isoformat(), "count": len(per_day.get(d, ()))})
            d += timedelta(days=1)

        # ---- streak ----
        solved_days = {e["day"] for e in events if e["kind"] != "failed"}
        streak, d = 0, today if today in solved_days else today - timedelta(days=1)
        while d in solved_days:
            streak += 1
            d -= timedelta(days=1)
        active_30 = sum(1 for i in range(30) if today - timedelta(days=i) in solved_days)

        # ---- progress: actual, forecast from your schedule, target pace ----
        first_list_solve: dict[str, date] = {}
        for e in events:
            if e["in_list"] and e["kind"] == "new" and e["slug"] not in first_list_solve:
                first_list_solve[e["slug"]] = e["day"]
        undated = max(0, pace["list_done"] - len(first_list_solve))  # solved before history import
        chart_start = min(start, today)
        before = undated + sum(1 for v in first_list_solve.values() if v < chart_start)
        by_day = defaultdict(int)
        for v in first_list_solve.values():
            if v >= chart_start:
                by_day[v] += 1
        start_done = before
        labels, actual, forecast, target = [], [], [], []
        total_days = max(1, (goal_end - chart_start).days)
        cum = before
        fc = None
        sched = {s["day"]: s for s in planner.schedule((goal_end - today).days + 1, today, c)} if goal_end >= today else {}
        d = chart_start
        while d <= goal_end:
            labels.append(d.isoformat())
            target.append(round(start_done + (pace["goal_total"] - start_done) * (d - chart_start).days / total_days, 1))
            if d <= today:
                cum += by_day.get(d, 0)
                actual.append(cum)
            else:
                actual.append(None)
            if d == today:
                fc = float(cum)
                forecast.append(round(fc, 1))
            elif d > today and fc is not None:
                fc += planner.NEW_PER_LEVEL[sched[d.isoformat()]["level"]]
                forecast.append(round(fc, 1))
            else:
                forecast.append(None)
            d += timedelta(days=1)

        diff = {"Easy": 0, "Medium": 0, "Hard": 0}
        for r in c.execute("SELECT p.difficulty, COUNT(*) n FROM srs s JOIN problems p ON p.slug=s.slug WHERE s.solves>0 GROUP BY p.difficulty"):
            if r["difficulty"] in diff:
                diff[r["difficulty"]] = r["n"]
        striver_total = c.execute("SELECT COUNT(*) FROM problems WHERE striver=1").fetchone()[0]
        striver_done = c.execute(
            "SELECT COUNT(*) FROM problems p JOIN srs s ON s.slug=p.slug WHERE p.striver=1 AND s.solves>0").fetchone()[0]

        last4 = weekly[-4:]
        planned4 = sum(w["planned"] for w in last4)
        return {
            "pace": pace, "weekly": weekly, "heat": heat, "streak": streak, "active_30": active_30,
            "progress": {"labels": labels, "actual": actual, "forecast": forecast, "target": target},
            "difficulty": diff, "striver": {"done": striver_done, "total": striver_total},
            "completion_4w": round(100 * sum(w["done"] for w in last4) / planned4) if planned4 else None,
            "patterns": planner.pattern_analysis(c),
        }
