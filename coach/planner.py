"""Pattern analysis, pacing and daily plan generation. Pure code, no LLM."""

from datetime import date, datetime, time, timedelta

from . import config, db
from .patterns import PATTERN_NAMES

MODES = ("exam", "normal", "free", "off")
DIFF_RANK = {"Easy": 0, "Medium": 1, "Hard": 2, None: 1}
ACTIVE_PATTERNS = 3        # how many patterns you learn in parallel
PATTERN_DONE_AT = 0.6      # coverage at which a pattern stops getting new problems first


# ---------------- modes ----------------

def _availability(conn) -> list:
    if "avail" not in conn.cache:
        conn.cache["avail"] = [dict(r) for r in conn.execute(
            "SELECT start_day, end_day, mode, note FROM availability ORDER BY id DESC")]
    return conn.cache["avail"]


def mode_for(day: date, conn=None) -> tuple[str, str | None]:
    if conn is None:
        with db.tx() as c:
            return mode_for(day, c)
    d = day.isoformat()
    for r in _availability(conn):  # newest entry wins
        if r["start_day"] <= d <= r["end_day"]:
            return r["mode"], r["note"]
    if day.weekday() >= 5:
        return db.get_setting("weekend_mode", conn), "weekend"
    return db.get_setting("default_mode", conn), None


def counts_for(mode: str, conn=None) -> tuple[int, int]:
    n, r = db.get_setting(f"counts_{mode}", conn) or (0, 0)
    return int(n), int(r)


# ---------------- analysis ----------------

def pattern_analysis(conn=None) -> list[dict]:
    own = conn is None
    conn = conn or db.connect()
    try:
        now = db.now_ts()
        rows = conn.execute(
            """SELECT p.slug, p.pattern, p.in_list, p.difficulty,
                      COALESCE(s.solves,0) solves, COALESCE(s.fails,0) fails, s.last_attempt, s.due
               FROM problems p LEFT JOIN srs s ON s.slug=p.slug"""
        ).fetchall()
        stats = {
            name: dict(pattern=name, list_total=0, list_solved=0, extra_solved=0, solves=0, fails=0,
                       last_practiced=None, due_reviews=0, solved_by_diff={"Easy": 0, "Medium": 0, "Hard": 0})
            for name in PATTERN_NAMES
        }
        for r in rows:
            st = stats.setdefault(r["pattern"], dict(
                pattern=r["pattern"], list_total=0, list_solved=0, extra_solved=0, solves=0, fails=0,
                last_practiced=None, due_reviews=0, solved_by_diff={"Easy": 0, "Medium": 0, "Hard": 0}))
            solved = r["solves"] > 0
            if r["in_list"]:
                st["list_total"] += 1
                st["list_solved"] += solved
            elif solved:
                st["extra_solved"] += 1
            st["solves"] += r["solves"]
            st["fails"] += r["fails"]
            if solved and r["difficulty"] in st["solved_by_diff"]:
                st["solved_by_diff"][r["difficulty"]] += 1
            if r["last_attempt"] and (st["last_practiced"] or 0) < r["last_attempt"]:
                st["last_practiced"] = r["last_attempt"]
            if solved and r["due"] and r["due"] <= now:
                st["due_reviews"] += 1

        out = []
        for i, name in enumerate(PATTERN_NAMES):
            st = stats[name]
            attempts = st["solves"] + st["fails"]
            solved_count = st["list_solved"] + st["extra_solved"]
            coverage = st["list_solved"] / st["list_total"] if st["list_total"] else 0
            fail_rate = st["fails"] / attempts if attempts else 0
            retention = 1 - min(1, st["due_reviews"] / solved_count) if solved_count else 0
            # A little credit for off-list practice in the same pattern.
            practice = min(1, coverage + 0.02 * st["extra_solved"])
            score = 0.55 * practice + 0.25 * (1 - fail_rate) + 0.20 * retention if attempts else 0
            if not attempts:
                label = "not started"
            elif score < 0.35:
                label = "weak"
            elif score < 0.65:
                label = "developing"
            else:
                label = "strong"
            days_since = (now - st["last_practiced"]) // 86400 if st["last_practiced"] else None
            out.append({**st, "order": i, "coverage": round(coverage, 3), "fail_rate": round(fail_rate, 3),
                        "retention": round(retention, 3), "score": round(score, 3), "label": label,
                        "days_since_practice": days_since})
        return out
    finally:
        if own:
            conn.close()


def recent_performance(day: date, conn) -> dict:
    """How well you followed the last 7 days of plans."""
    start = (day - timedelta(days=7)).isoformat()
    rows = conn.execute(
        "SELECT day, status FROM plan_items WHERE day>=? AND day<?", (start, day.isoformat())
    ).fetchall()
    total = len(rows)
    engaged = sum(r["status"] in ("solved", "failed") for r in rows)
    solved = sum(r["status"] == "solved" for r in rows)
    # Consecutive days (going back from yesterday) with a plan but nothing done.
    by_day: dict[str, list[str]] = {}
    for r in conn.execute("SELECT day, status FROM plan_items WHERE day<? ORDER BY day DESC LIMIT 60",
                          (day.isoformat(),)):
        by_day.setdefault(r["day"], []).append(r["status"])
    missed_streak = 0
    for d in sorted(by_day, reverse=True):
        if any(s in ("solved", "failed") for s in by_day[d]):
            break
        missed_streak += 1
    return {"total": total, "engaged": engaged, "solved": solved,
            "completion": engaged / total if total else None, "missed_streak": missed_streak}


def pace(conn=None) -> dict:
    own = conn is None
    conn = conn or db.connect()
    try:
        today = db.today()
        goal_total = int(db.get_setting("goal_total", conn) or 0)
        goal_end = date.fromisoformat(db.get_setting("goal_end", conn))
        done = conn.execute(
            "SELECT COUNT(*) FROM problems p JOIN srs s ON s.slug=p.slug WHERE p.in_list=1 AND s.solves>0"
        ).fetchone()[0]
        total_solved = conn.execute("SELECT COUNT(*) FROM srs WHERE solves>0").fetchone()[0]
        remaining = max(0, goal_total - done)
        days_left = max(0, (goal_end - today).days)
        capacity = 0
        mode_days = {m: 0 for m in MODES}
        for i in range(days_left + 1):
            d = today + timedelta(days=i)
            m, _ = mode_for(d, conn)
            mode_days[m] += 1
            capacity += counts_for(m, conn)[0]
        due = conn.execute("SELECT COUNT(*) FROM srs WHERE solves>0 AND due<=?", (db.now_ts(),)).fetchone()[0]
        return {
            "goal_total": goal_total, "goal_end": goal_end.isoformat(), "list_done": done,
            "total_solved": total_solved, "remaining": remaining, "days_left": days_left,
            "planned_capacity": capacity, "on_track": capacity >= remaining,
            "shortfall": max(0, remaining - capacity), "mode_days": mode_days, "reviews_due": due,
        }
    finally:
        if own:
            conn.close()


# ---------------- plan generation ----------------

def _pick_reviews(conn, day: date, n: int, exam: bool, exclude: set[str], weakness: dict[str, float]) -> list[tuple[str, str]]:
    if n <= 0:
        return []
    end_of_day = int(datetime.combine(day, time(23, 59), config.TZ).timestamp())
    now = db.now_ts()
    rows = conn.execute(
        """SELECT s.*, p.difficulty, p.pattern, p.title, p.in_list FROM srs s JOIN problems p ON p.slug=s.slug
           WHERE (s.solves>0 OR s.fails>0) AND s.due<=?""",
        (end_of_day,),
    ).fetchall()
    cands = []
    for r in rows:
        if r["slug"] in exclude:
            continue
        interval = max(1, r["interval_days"]) * 86400
        overdue = max(0, now - r["due"]) / interval
        prio = min(overdue, 3) + 0.6 * min(r["fails"], 3) + weakness.get(r["pattern"], 0.5)
        recent = r["last_attempt"] and now - r["last_attempt"] < 21 * 86400
        if not exam and not r["in_list"] and r["difficulty"] == "Easy" and not r["fails"]:
            continue  # random easy problems outside the list aren't worth revising
        prio += 1.0 if r["in_list"] else 0
        if exam:
            # Quick wins only: easy problems or ones you saw recently.
            if not (r["difficulty"] == "Easy" or recent):
                continue
            prio += 1 if r["difficulty"] == "Easy" else 0
        cands.append((prio, r))
    cands.sort(key=lambda x: -x[0])
    out = []
    for _, r in cands[:n]:
        if r["solves"] == 0:
            why = "you couldn't solve this last time; try again"
        else:
            days = (now - r["last_solved"]) // 86400
            why = f"revise: last solved {days} day{'s' if days != 1 else ''} ago"
        out.append((r["slug"], why))
    if exam and len(out) < n:
        # Nothing due that's quick: re-do the most recent easy solve.
        rows = conn.execute(
            """SELECT s.slug FROM srs s JOIN problems p ON p.slug=s.slug
               WHERE s.solves>0 AND p.difficulty='Easy' ORDER BY s.last_solved DESC LIMIT 10"""
        ).fetchall()
        for r in rows:
            if len(out) >= n:
                break
            if r["slug"] not in exclude and r["slug"] not in {s for s, _ in out}:
                out.append((r["slug"], "quick warm-up you've solved before"))
    return out


def _pick_new(conn, day: date, n: int, analysis: list[dict], exclude: set[str], easy_only: bool) -> list[tuple[str, str]]:
    if n <= 0:
        return []
    out: list[tuple[str, str]] = []
    # 1) carry over unsolved new problems from the last few days
    rows = conn.execute(
        """SELECT pi.slug, p.difficulty, MIN(pi.day) first_day FROM plan_items pi JOIN problems p ON p.slug=pi.slug
           LEFT JOIN srs s ON s.slug=pi.slug
           WHERE pi.kind='new' AND pi.status IN ('missed','skipped') AND pi.day>=? AND pi.day<?
             AND COALESCE(s.solves,0)=0 AND COALESCE(s.fails,0)=0
           GROUP BY pi.slug, p.difficulty ORDER BY first_day""",
        ((day - timedelta(days=5)).isoformat(), day.isoformat()),
    ).fetchall()
    for r in rows:
        if len(out) >= n:
            break
        if r["slug"] in exclude or (easy_only and r["difficulty"] != "Easy"):
            continue
        out.append((r["slug"], "carried over from a missed day"))

    # 2) next unsolved problems from the active patterns (lowest coverage first)
    active = [a for a in analysis if a["list_total"] and a["coverage"] < PATTERN_DONE_AT][:ACTIVE_PATTERNS]
    if not active:
        active = sorted([a for a in analysis if a["list_solved"] < a["list_total"]], key=lambda a: a["coverage"])[:ACTIVE_PATTERNS]
    active.sort(key=lambda a: a["coverage"])
    queues = {}
    for a in active:
        rows = conn.execute(
            """SELECT p.slug, p.difficulty FROM problems p LEFT JOIN srs s ON s.slug=p.slug
               WHERE p.in_list=1 AND p.pattern=? AND COALESCE(s.solves,0)=0 AND COALESCE(s.fails,0)=0
               ORDER BY p.list_order""",
            (a["pattern"],),
        ).fetchall()
        q = [r for r in rows if not easy_only or r["difficulty"] == "Easy"] or (rows[:1] if easy_only else rows)
        queues[a["pattern"]] = [r["slug"] for r in q]

    used = exclude | {s for s, _ in out}
    while len(out) < n and any(queues.values()):
        for a in active:
            q = queues[a["pattern"]]
            while q and q[0] in used:
                q.pop(0)
            if q and len(out) < n:
                slug = q.pop(0)
                used.add(slug)
                out.append((slug, f"new · {a['pattern']} ({a['list_solved']}/{a['list_total']} done)"))
    return out


def generate_plan(day: date | None = None, force: bool = False) -> dict:
    day = day or db.today()
    with db.tx() as c:
        existing = c.execute("SELECT * FROM plans WHERE day=?", (day.isoformat(),)).fetchone()
        if existing and not force:
            return get_plan(day, c)

        cutoff = min(day, db.today()).isoformat()
        c.execute("UPDATE plan_items SET status='missed' WHERE status='pending' AND day<?", (cutoff,))
        if force:
            c.execute("DELETE FROM plan_items WHERE day=? AND status='pending'", (day.isoformat(),))

        mode, mode_note = mode_for(day, c)
        new_n, rev_n = counts_for(mode, c)
        perf = recent_performance(day, c)
        analysis = pattern_analysis(c)
        notes = []
        if mode_note and mode_note != "weekend":
            notes.append(mode_note)
        easy_only = mode == "exam"

        if mode in ("normal", "free"):
            if perf["missed_streak"] >= 3:
                new_n, rev_n, easy_only = 1, 1, True
                notes.append(f"You've missed {perf['missed_streak']} days, so today is a light restart.")
            elif perf["completion"] is not None and perf["total"] >= 4 and perf["completion"] < 0.4:
                new_n = max(1, new_n - 1)
                notes.append("Lighter load: you finished under 40% of last week's plan.")
            elif perf["completion"] is not None and perf["total"] >= 6 and perf["completion"] >= 0.9:
                if not pace(c)["on_track"]:
                    new_n += 1
                    notes.append("You're consistent but behind on the goal, so one extra new problem.")
            due_count = c.execute(
                """SELECT COUNT(*) FROM srs s JOIN problems p ON p.slug=s.slug WHERE s.solves>0 AND s.due<=?
                   AND (p.in_list=1 OR s.fails>0 OR p.difficulty!='Easy')""", (db.now_ts(),)).fetchone()[0]
            if due_count > 15 and new_n > 1:
                new_n -= 1
                rev_n += 1
                notes.append(f"{due_count} reviews are overdue, so one new problem was swapped for a review.")

        already = {r["slug"] for r in c.execute("SELECT slug FROM plan_items WHERE day=?", (day.isoformat(),))}
        weakness = {a["pattern"]: 1 - a["score"] for a in analysis}
        reviews = _pick_reviews(c, day, rev_n, easy_only, already, weakness)
        new = _pick_new(c, day, new_n, analysis, already | {s for s, _ in reviews}, easy_only)
        if mode == "exam" and not reviews:
            new = _pick_new(c, day, 1, analysis, already, True)

        c.execute(
            "INSERT INTO plans(day, mode, note) VALUES (?,?,?) ON CONFLICT(day) DO UPDATE SET mode=excluded.mode, note=excluded.note",
            (day.isoformat(), mode, " ".join(notes) or None),
        )
        for kind, items in (("new", new), ("review", reviews)):
            for slug, why in items:
                c.execute(
                    "INSERT OR IGNORE INTO plan_items(day, slug, kind, reason, updated_at) VALUES (?,?,?,?,?)",
                    (day.isoformat(), slug, kind, why, db.now_ts()),
                )
        return get_plan(day, c)


def get_plan(day: date | None = None, conn=None) -> dict:
    day = day or db.today()
    own = conn is None
    conn = conn or db.connect()
    try:
        plan = conn.execute("SELECT * FROM plans WHERE day=?", (day.isoformat(),)).fetchone()
        items = conn.execute(
            """SELECT pi.*, p.title, p.difficulty, p.pattern FROM plan_items pi
               JOIN problems p ON p.slug=pi.slug WHERE pi.day=? ORDER BY pi.kind, pi.id""",
            (day.isoformat(),),
        ).fetchall()
        return {
            "day": day.isoformat(),
            "exists": plan is not None,
            "mode": plan["mode"] if plan else mode_for(day, conn)[0],
            "note": plan["note"] if plan else None,
            "emailed_at": plan["emailed_at"] if plan else None,
            "items": [dict(i) | {"url": f"https://leetcode.com/problems/{i['slug']}/"} for i in items],
        }
    finally:
        if own:
            conn.close()


def mark_item(item_id: int, action: str) -> dict:
    """Handle solved / failed / skip from the web UI or email buttons."""
    from . import tracker

    with db.tx() as c:
        item = c.execute("SELECT * FROM plan_items WHERE id=?", (item_id,)).fetchone()
        if not item:
            raise ValueError("unknown plan item")
        now = db.now_ts()
        if action == "solved":
            tracker.record_attempt(item["slug"], now, "solved", "email", c)
            c.execute("UPDATE plan_items SET status='solved', updated_at=? WHERE id=?", (now, item_id))
        elif action == "failed":
            tracker.record_attempt(item["slug"], now, "failed", "email", c)
            c.execute("UPDATE plan_items SET status='failed', updated_at=? WHERE id=?", (now, item_id))
        elif action == "skip":
            c.execute("UPDATE plan_items SET status='skipped', updated_at=? WHERE id=?", (now, item_id))
        else:
            raise ValueError("action must be solved, failed or skip")
        return dict(c.execute(
            "SELECT pi.*, p.title FROM plan_items pi JOIN problems p ON p.slug=pi.slug WHERE pi.id=?", (item_id,)
        ).fetchone())


def upcoming_modes(days: int = 21) -> list[dict]:
    with db.tx() as c:
        out = []
        for i in range(days):
            d = db.today() + timedelta(days=i)
            m, note = mode_for(d, c)
            n, r = counts_for(m, c)
            out.append({"day": d.isoformat(), "weekday": d.strftime("%a"), "mode": m, "note": note, "new": n, "review": r})
        return out
