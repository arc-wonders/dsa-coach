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


LEVEL_NAMES = ["Off", "Light", "Steady", "Focused", "Deep"]
MAX_ITEMS = [0, 1, 2, 3, 5]
# Expected new problems per day at each level (used for pacing forecasts).
NEW_PER_LEVEL = [0, 0.2, 0.8, 1.4, 2.9]
# Estimated minutes per problem.
COST = {
    "new": {"Easy": 15, "Medium": 30, "Hard": 60, None: 30},
    "review": {"Easy": 8, "Medium": 18, "Hard": 35, None: 18},
}


def allowed(kind: str, difficulty: str | None, level: int) -> bool:
    """Hard problems only when you have real time; light days are easy-only."""
    if level <= 1:
        return difficulty == "Easy"
    if difficulty == "Hard":
        return level >= 4 or (kind == "review" and level >= 3)
    return True


def _overrides(conn) -> dict[str, int]:
    if "overrides" not in conn.cache:
        conn.cache["overrides"] = {r["day"]: int(r["level"]) for r in conn.execute("SELECT day, level FROM day_load")}
    return conn.cache["overrides"]


def day_info(day: date, conn) -> dict:
    """Effort level for a day: your manual override, else the mode's default,
    tapered to Light the day before an exam block."""
    mode, note = mode_for(day, conn)
    mode_levels = db.get_setting("mode_levels", conn)
    auto = int(mode_levels.get(mode, 2))
    reason = note if note and note != "weekend" else None
    if mode not in ("exam", "off"):
        nxt, _ = mode_for(day + timedelta(days=1), conn)
        if nxt == "exam" and auto > 1:
            auto, reason = 1, "exams start tomorrow"
    ov = _overrides(conn).get(day.isoformat())
    level = auto if ov is None else ov
    minutes = db.get_setting("level_minutes", conn)[level]
    return {"day": day.isoformat(), "weekday": day.strftime("%a"), "mode": mode, "note": reason,
            "auto_level": auto, "level": level, "override": ov is not None,
            "level_name": LEVEL_NAMES[level], "minutes": minutes}


def schedule(days: int = 28, start: date | None = None, conn=None) -> list[dict]:
    if conn is None:
        with db.tx() as c:
            return schedule(days, start, c)
    start = start or db.today()
    return [day_info(start + timedelta(days=i), conn) for i in range(days)]


def set_day_level(day: date, level: int | None) -> None:
    with db.tx() as c:
        if level is None:
            c.execute("DELETE FROM day_load WHERE day=?", (day.isoformat(),))
        else:
            level = max(0, min(4, int(level)))
            c.execute("INSERT INTO day_load(day, level) VALUES (?, ?) ON CONFLICT(day) DO UPDATE SET level=excluded.level",
                      (day.isoformat(), level))


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
        "SELECT day, status FROM plan_items WHERE day>=? AND day<? AND status!='swapped'", (start, day.isoformat())
    ).fetchall()
    total = len(rows)
    engaged = sum(r["status"] in ("solved", "failed") for r in rows)
    solved = sum(r["status"] == "solved" for r in rows)
    # Consecutive days (going back from yesterday) with a plan but nothing done.
    by_day: dict[str, list[str]] = {}
    for r in conn.execute("SELECT day, status FROM plan_items WHERE day<? AND status!='swapped' ORDER BY day DESC LIMIT 60",
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
    if conn is None:
        with db.tx() as c:
            return pace(c)
    today = db.today()
    goal_total = int(db.get_setting("goal_total", conn) or 0)
    goal_end = date.fromisoformat(db.get_setting("goal_end", conn))
    done = conn.execute(
        "SELECT COUNT(*) FROM problems p JOIN srs s ON s.slug=p.slug WHERE p.in_list=1 AND s.solves>0"
    ).fetchone()[0]
    list_total = conn.execute("SELECT COUNT(*) FROM problems WHERE in_list=1").fetchone()[0]
    total_solved = conn.execute("SELECT COUNT(*) FROM srs WHERE solves>0").fetchone()[0]
    remaining = max(0, goal_total - done)
    days_left = max(0, (goal_end - today).days)
    capacity = 0.0
    level_days = [0] * 5
    for info in schedule(days_left + 1, today, conn):
        level_days[info["level"]] += 1
        capacity += NEW_PER_LEVEL[info["level"]]
    capacity = int(round(capacity))
    due = conn.execute("SELECT COUNT(*) FROM srs WHERE solves>0 AND due<=?", (db.now_ts(),)).fetchone()[0]
    return {
        "goal_total": goal_total, "goal_end": goal_end.isoformat(), "list_done": done, "list_total": list_total,
        "total_solved": total_solved, "remaining": remaining, "days_left": days_left,
        "planned_capacity": capacity, "on_track": capacity >= remaining,
        "shortfall": max(0, remaining - capacity), "level_days": level_days, "reviews_due": due,
    }


# ---------------- plan generation ----------------

def _review_candidates(conn, day: date, exclude: set[str], weakness: dict[str, float]) -> list[dict]:
    end_of_day = int(datetime.combine(day, time(23, 59), config.TZ).timestamp())
    now = db.now_ts()
    rows = conn.execute(
        """SELECT s.*, p.difficulty, p.pattern, p.title, p.in_list FROM srs s JOIN problems p ON p.slug=s.slug
           WHERE (s.solves>0 OR s.fails>0) AND s.due<=?""",
        (end_of_day,),
    ).fetchall()
    out = []
    for r in rows:
        if r["slug"] in exclude:
            continue
        if not r["in_list"] and r["difficulty"] == "Easy" and not r["fails"]:
            continue  # random easy problems outside the list aren't worth revising
        interval = max(1, r["interval_days"]) * 86400
        overdue = max(0, now - r["due"]) / interval
        prio = min(overdue, 3) + 0.6 * min(r["fails"], 3) + weakness.get(r["pattern"], 0.5)
        prio += 1.0 if r["in_list"] else 0
        if r["solves"] == 0:
            why = "you couldn't solve this last time, try again"
        else:
            days = (now - r["last_solved"]) // 86400
            why = f"revise: last solved {days} day{'s' if days != 1 else ''} ago"
        out.append({"slug": r["slug"], "kind": "review", "difficulty": r["difficulty"], "reason": why,
                    "prio": prio, "cost": COST["review"][r["difficulty"]]})
    out.sort(key=lambda x: -x["prio"])
    return out


def _warmups(conn, exclude: set[str]) -> list[dict]:
    """Recently solved easy problems, for light days with nothing due."""
    rows = conn.execute(
        """SELECT s.slug, p.difficulty FROM srs s JOIN problems p ON p.slug=s.slug
           WHERE s.solves>0 AND p.difficulty='Easy' ORDER BY s.last_solved DESC LIMIT 15"""
    ).fetchall()
    return [{"slug": r["slug"], "kind": "review", "difficulty": "Easy", "reason": "quick warm-up you've solved before",
             "prio": 0, "cost": COST["review"]["Easy"]} for r in rows if r["slug"] not in exclude]


def _new_candidates(conn, day: date, analysis: list[dict], exclude: set[str]) -> list[dict]:
    out: list[dict] = []
    used = set(exclude)
    # 1) unsolved new problems carried over from the last few days
    rows = conn.execute(
        """SELECT pi.slug, p.difficulty, MIN(pi.day) first_day FROM plan_items pi JOIN problems p ON p.slug=pi.slug
           LEFT JOIN srs s ON s.slug=pi.slug
           WHERE pi.kind='new' AND pi.status IN ('missed','skipped') AND pi.day>=? AND pi.day<?
             AND COALESCE(s.solves,0)=0 AND COALESCE(s.fails,0)=0
           GROUP BY pi.slug, p.difficulty ORDER BY first_day""",
        ((day - timedelta(days=5)).isoformat(), day.isoformat()),
    ).fetchall()
    for r in rows:
        if r["slug"] not in used:
            used.add(r["slug"])
            out.append({"slug": r["slug"], "kind": "new", "difficulty": r["difficulty"],
                        "reason": "carried over from a missed day", "cost": COST["new"][r["difficulty"]]})

    # 2) round-robin over the active patterns (lowest coverage first), list order inside each
    active = [a for a in analysis if a["list_total"] and a["coverage"] < PATTERN_DONE_AT][:ACTIVE_PATTERNS]
    if not active:
        active = sorted([a for a in analysis if a["list_solved"] < a["list_total"]], key=lambda a: a["coverage"])[:ACTIVE_PATTERNS]
    active.sort(key=lambda a: a["coverage"])
    queues = {}
    for a in active:
        queues[a["pattern"]] = [dict(r) for r in conn.execute(
            """SELECT p.slug, p.difficulty FROM problems p LEFT JOIN srs s ON s.slug=p.slug
               WHERE p.in_list=1 AND p.pattern=? AND COALESCE(s.solves,0)=0 AND COALESCE(s.fails,0)=0
               ORDER BY p.list_order""",
            (a["pattern"],),
        )]
    while any(queues.values()):
        for a in active:
            q = queues[a["pattern"]]
            while q and q[0]["slug"] in used:
                q.pop(0)
            if q:
                r = q.pop(0)
                used.add(r["slug"])
                out.append({"slug": r["slug"], "kind": "new", "difficulty": r["difficulty"],
                            "reason": f"new · {a['pattern']} ({a['list_solved']}/{a['list_total']} done)",
                            "cost": COST["new"][r["difficulty"]]})
    return out


def _fill(level: int, budget: int, reviews: list[dict], new: list[dict], review_share: float) -> list[dict]:
    """Pick items that fit the time budget and the difficulty rules for this level."""
    reviews = [r for r in reviews if allowed("review", r["difficulty"], level)]
    new = [n for n in new if allowed("new", n["difficulty"], level)]
    picked: list[dict] = []
    spent = 0

    def take(pool, limit, max_items):
        nonlocal spent
        for cand in list(pool):
            if len(picked) >= max_items:
                return
            if spent + cand["cost"] <= limit:
                picked.append(cand)
                pool.remove(cand)
                spent += cand["cost"]

    cap = MAX_ITEMS[level]
    take(reviews, budget * review_share, cap if review_share >= 1 else max(1, round(cap * review_share)))
    take(new, budget, cap)
    take(reviews, budget, cap)
    if not picked and level > 0:
        pool = sorted(reviews + new, key=lambda x: x["cost"])
        if pool:
            picked.append(pool[0])
    return picked


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

        info = day_info(day, c)
        level = info["level"]
        perf = recent_performance(day, c)
        analysis = pattern_analysis(c)
        notes = [info["note"].capitalize() + "."] if info["note"] else []

        if level >= 2 and not info["override"]:
            if perf["missed_streak"] >= 3:
                level = 1
                notes.append(f"You've missed {perf['missed_streak']} days, so today is a light restart.")
            elif perf["completion"] is not None and perf["total"] >= 4 and perf["completion"] < 0.4:
                level -= 1
                notes.append("Lighter than usual: you finished under 40% of last week's plan.")
            elif perf["completion"] is not None and perf["total"] >= 6 and perf["completion"] >= 0.9 \
                    and level < 4 and not pace(c)["on_track"]:
                level += 1
                notes.append("You've been consistent but are behind the goal, so a bit more today.")
        budget = db.get_setting("level_minutes", c)[level]

        already = {r["slug"] for r in c.execute("SELECT slug FROM plan_items WHERE day=?", (day.isoformat(),))}
        weakness = {a["pattern"]: 1 - a["score"] for a in analysis}
        reviews = _review_candidates(c, day, already, weakness)
        overdue = len(reviews)
        if level == 1:
            reviews += _warmups(c, already | {r["slug"] for r in reviews})
        new = _new_candidates(c, day, analysis, already | {r["slug"] for r in reviews})
        share = 1.0 if level == 1 else (0.6 if overdue > 15 else 0.4)
        items = _fill(level, budget, reviews, new, share)

        c.execute(
            """INSERT INTO plans(day, mode, note, level) VALUES (?,?,?,?)
               ON CONFLICT(day) DO UPDATE SET mode=excluded.mode, note=excluded.note, level=excluded.level""",
            (day.isoformat(), info["mode"], " ".join(notes) or None, level),
        )
        for it in items:
            c.execute(
                "INSERT OR IGNORE INTO plan_items(day, slug, kind, reason, est_min, updated_at) VALUES (?,?,?,?,?,?)",
                (day.isoformat(), it["slug"], it["kind"], it["reason"], it["cost"], db.now_ts()),
            )
        return get_plan(day, c)


def get_plan(day: date | None = None, conn=None) -> dict:
    if conn is None:
        with db.tx() as c:
            return get_plan(day, c)
    day = day or db.today()
    plan = conn.execute("SELECT * FROM plans WHERE day=?", (day.isoformat(),)).fetchone()
    items = conn.execute(
        """SELECT pi.*, p.title, p.difficulty, p.pattern, p.striver FROM plan_items pi
           JOIN problems p ON p.slug=pi.slug WHERE pi.day=? AND pi.status!='swapped' ORDER BY pi.kind, pi.id""",
        (day.isoformat(),),
    ).fetchall()
    info = day_info(day, conn)
    level = plan["level"] if plan and plan["level"] is not None else info["level"]
    items = [dict(i) | {"url": f"https://leetcode.com/problems/{i['slug']}/",
                        "est_min": i["est_min"] or COST[i["kind"]][i["difficulty"]]} for i in items]
    return {
        "day": day.isoformat(), "exists": plan is not None,
        "mode": plan["mode"] if plan else info["mode"],
        "level": level, "level_name": LEVEL_NAMES[level],
        "budget": db.get_setting("level_minutes", conn)[level],
        "est_total": sum(i["est_min"] for i in items if i["status"] in ("pending", "solved", "failed")),
        "note": plan["note"] if plan else None,
        "emailed_at": plan["emailed_at"] if plan else None,
        "items": items,
    }


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
        elif action == "undo":
            c.execute("UPDATE plan_items SET status='pending', updated_at=? WHERE id=?", (now, item_id))
        else:
            raise ValueError("action must be solved, failed, skip or undo")
        return dict(c.execute(
            "SELECT pi.*, p.title FROM plan_items pi JOIN problems p ON p.slug=pi.slug WHERE pi.id=?", (item_id,)
        ).fetchone())


def swap_item(item_id: int) -> dict | None:
    """Replace a problem with an easier / quicker one (e.g. 'too hard for today')."""
    with db.tx() as c:
        item = c.execute(
            "SELECT pi.*, p.difficulty FROM plan_items pi JOIN problems p ON p.slug=pi.slug WHERE pi.id=?", (item_id,)
        ).fetchone()
        if not item or item["status"] != "pending":
            return None
        day = date.fromisoformat(item["day"])
        today_slugs = {r["slug"] for r in c.execute("SELECT slug FROM plan_items WHERE day=?", (item["day"],))}
        analysis = pattern_analysis(c)
        weakness = {a["pattern"]: 1 - a["score"] for a in analysis}
        rank = DIFF_RANK.get(item["difficulty"], 1)
        cost = COST[item["kind"]][item["difficulty"]]
        reviews = _review_candidates(c, day, today_slugs, weakness) + _warmups(c, today_slugs)
        new = _new_candidates(c, day, analysis, today_slugs)
        same, other = (reviews, new) if item["kind"] == "review" else (new, reviews)

        def easier(x):
            return DIFF_RANK.get(x["difficulty"], 1) < rank or (rank == 0 and x["cost"] <= cost)

        pick = next((x for x in same + other if easier(x)), None)
        if not pick:
            return None
        c.execute("UPDATE plan_items SET status='swapped', updated_at=? WHERE id=?", (db.now_ts(), item_id))
        c.execute(
            "INSERT OR IGNORE INTO plan_items(day, slug, kind, reason, est_min, updated_at) VALUES (?,?,?,?,?,?)",
            (item["day"], pick["slug"], pick["kind"], "easier swap · " + pick["reason"], pick["cost"], db.now_ts()),
        )
        return pick


def add_item(day: date | None = None) -> dict | None:
    """'I have more time': add one more problem (new first), skipping Hard."""
    day = day or db.today()
    with db.tx() as c:
        today_slugs = {r["slug"] for r in c.execute("SELECT slug FROM plan_items WHERE day=?", (day.isoformat(),))}
        analysis = pattern_analysis(c)
        weakness = {a["pattern"]: 1 - a["score"] for a in analysis}
        pool = _new_candidates(c, day, analysis, today_slugs) + _review_candidates(c, day, today_slugs, weakness)
        pick = next((x for x in pool if x["difficulty"] != "Hard"), None)
        if not pick:
            return None
        c.execute(
            "INSERT OR IGNORE INTO plan_items(day, slug, kind, reason, est_min, updated_at) VALUES (?,?,?,?,?,?)",
            (day.isoformat(), pick["slug"], pick["kind"], "extra · " + pick["reason"], pick["cost"], db.now_ts()),
        )
        return pick


def upcoming_modes(days: int = 21) -> list[dict]:
    return schedule(days)
