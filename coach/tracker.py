"""Recording attempts, spaced-repetition updates and LeetCode sync."""

import json
import logging
from collections import defaultdict
from datetime import timedelta

from . import db, leetcode
from .patterns import PATTERNS, STRIVER, pattern_for_tags

log = logging.getLogger(__name__)

DAY = 86400
# Review intervals (days) after each successful solve.
STEPS = [3, 7, 15, 30, 60]
FAIL_INTERVAL = 2


def seed_problems(fetch_meta: bool = True) -> list[str]:
    """Insert/refresh the curated list. Only fetches metadata for problems we don't know yet.
    Returns slugs LeetCode didn't recognise."""
    slugs = [s for _, items in PATTERNS for s in items]
    with db.tx() as c:
        known = {r["slug"] for r in c.execute("SELECT slug FROM problems WHERE difficulty IS NOT NULL")}
    meta = leetcode.question_meta([s for s in slugs if s not in known]) if fetch_meta else {}
    missing = [s for s in slugs if fetch_meta and s not in meta and s not in known]
    with db.tx() as c:
        for pattern, items in PATTERNS:
            for i, slug in enumerate(items):
                m = meta.get(slug, {})
                c.execute(
                    """INSERT INTO problems(slug, title, difficulty, pattern, in_list, list_order, tags, striver)
                       VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                       ON CONFLICT(slug) DO UPDATE SET pattern=excluded.pattern, in_list=1, striver=excluded.striver,
                         list_order=excluded.list_order,
                         title=COALESCE(excluded.title, problems.title),
                         difficulty=COALESCE(excluded.difficulty, problems.difficulty),
                         tags=CASE WHEN excluded.tags='[]' THEN problems.tags ELSE excluded.tags END""",
                    (slug, m.get("title") or (None if slug in known else slug.replace("-", " ").title()),
                     m.get("difficulty"), pattern, i, json.dumps(m.get("tags", [])), int(slug in STRIVER)),
                )
    return missing


def ensure_problems(slugs: set[str]) -> None:
    """Make sure off-list problems exist in the table (fetch tags to pick a pattern)."""
    with db.tx() as c:
        known = {r["slug"] for r in c.execute("SELECT slug FROM problems")}
    unknown = sorted(slugs - known)
    if not unknown:
        return
    meta = leetcode.question_meta(unknown)
    with db.tx() as c:
        for slug in unknown:
            m = meta.get(slug, {})
            c.execute(
                "INSERT OR IGNORE INTO problems(slug, title, difficulty, pattern, in_list, tags) VALUES (?,?,?,?,0,?)",
                (slug, m.get("title") or slug.replace("-", " ").title(), m.get("difficulty"),
                 pattern_for_tags(m.get("tags", [])), json.dumps(m.get("tags", []))),
            )


def _apply_srs(c, slug: str, ts: int, outcome: str) -> None:
    row = c.execute("SELECT * FROM srs WHERE slug=?", (slug,)).fetchone()
    if row and row["last_attempt"] and ts <= row["last_attempt"]:
        return  # older than what we already know; ignore for scheduling
    if outcome == "failed":
        if row is None:
            c.execute(
                "INSERT INTO srs(slug, last_attempt, step, interval_days, due, fails) VALUES (?,?,0,?,?,1)",
                (slug, ts, FAIL_INTERVAL, ts + FAIL_INTERVAL * DAY),
            )
        else:
            c.execute(
                "UPDATE srs SET last_attempt=?, step=0, interval_days=?, due=?, fails=fails+1 WHERE slug=?",
                (ts, FAIL_INTERVAL, ts + FAIL_INTERVAL * DAY, slug),
            )
        return

    if row is None:
        c.execute(
            """INSERT INTO srs(slug, first_solved, last_solved, last_attempt, step, interval_days, due, solves)
               VALUES (?,?,?,?,0,?,?,1)""",
            (slug, ts, ts, ts, STEPS[0], ts + STEPS[0] * DAY),
        )
        return
    if row["last_solved"] and ts - row["last_solved"] < DAY / 2:
        c.execute("UPDATE srs SET last_attempt=?, last_solved=? WHERE slug=?", (ts, ts, slug))
        return
    # A solve after a fail restarts the ladder at step 0; otherwise climb a step.
    if row["last_solved"] is None or (row["fails"] and row["interval_days"] == FAIL_INTERVAL):
        step = 0
    else:
        step = min(row["step"] + 1, len(STEPS) - 1)
    c.execute(
        """UPDATE srs SET first_solved=COALESCE(first_solved, ?), last_solved=?, last_attempt=?,
           step=?, interval_days=?, due=?, solves=solves+1 WHERE slug=?""",
        (ts, ts, ts, step, STEPS[step], ts + STEPS[step] * DAY, slug),
    )


def record_attempt(slug: str, ts: int, outcome: str, source: str, conn=None) -> bool:
    """Store an attempt and update SRS + today's plan. Returns False if already known."""
    if conn is None:
        with db.tx() as c:
            return record_attempt(slug, ts, outcome, source, c)
    cur = conn.execute(
        "INSERT OR IGNORE INTO attempts(slug, ts, outcome, source) VALUES (?,?,?,?)",
        (slug, ts, outcome, source),
    )
    if cur.rowcount == 0:
        return False
    _apply_srs(conn, slug, ts, outcome)
    # Close matching plan items from the last few days.
    d = db.ts_to_date(ts)
    status = "solved" if outcome == "solved" else "failed"
    conn.execute(
        """UPDATE plan_items SET status=?, updated_at=? WHERE slug=? AND day BETWEEN ? AND ?
           AND status IN ('pending','skipped','missed')""",
        (status, ts, slug, (d - timedelta(days=3)).isoformat(), d.isoformat()),
    )
    return True


def sync_recent() -> int:
    """Daily sync from the public endpoint (no cookie). Returns new solves found."""
    subs = leetcode.recent_accepted()
    ensure_problems({s["slug"] for s in subs})
    n = 0
    with db.tx() as c:
        for s in sorted(subs, key=lambda x: x["ts"]):
            n += record_attempt(s["slug"], s["ts"], "solved", "leetcode", c)
    return n


def full_import() -> dict:
    """One-time import of the whole history using the session cookie."""
    subs = leetcode.all_submissions()
    by_day: dict[tuple[str, object], list[dict]] = defaultdict(list)
    for s in subs:
        by_day[(s["slug"], db.ts_to_date(s["ts"]))].append(s)

    events = []  # (ts, slug, outcome)
    for (slug, _), items in by_day.items():
        acs = [s for s in items if s["accepted"]]
        if acs:
            events.append((min(s["ts"] for s in acs), slug, "solved"))
        else:  # tried that day, never got it accepted
            events.append((max(s["ts"] for s in items), slug, "failed"))

    # Catch solved problems whose submissions weren't returned (very old ones).
    seen = {slug for _, slug, o in events if o == "solved"}
    try:
        extra = leetcode.all_solved_slugs() - seen
    except Exception as e:  # noqa: BLE001
        log.warning("problems/all lookup failed: %s", e)
        extra = set()
    old_ts = db.now_ts() - 60 * DAY
    events += [(old_ts, slug, "solved") for slug in extra]

    ensure_problems({slug for _, slug, _ in events})
    events.sort()
    added = 0
    with db.tx() as c:
        for ts, slug, outcome in events:
            added += record_attempt(slug, ts, outcome, "leetcode", c)
    return {"submissions": len(subs), "events": len(events), "added": added, "undated": len(extra)}
