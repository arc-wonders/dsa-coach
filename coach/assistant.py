"""Gemini assistant. Gemini never picks problems itself: it calls these tools,
which change settings/availability, and the planner does the rest."""

import json
from datetime import date

from google import genai
from google.genai import types

from . import config, db, planner

_client: genai.Client | None = None


def _gc() -> genai.Client:
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY not set in .env")
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


# ---------------- tools ----------------

def get_status() -> dict:
    """Overall progress toward the placement goal: problems done, days left, whether on track, reviews due."""
    return planner.pace()


def get_pattern_analysis() -> list:
    """Per-pattern stats: coverage of the curated list, fail rate, reviews due, strength label (not started/weak/developing/strong)."""
    keep = ("pattern", "list_solved", "list_total", "extra_solved", "fail_rate", "due_reviews", "label", "days_since_practice")
    return [{k: a[k] for k in keep} for a in planner.pattern_analysis()]


def get_today_plan() -> dict:
    """Today's plan: mode and the list of problems with their status."""
    p = planner.get_plan()
    p["items"] = [{k: i[k] for k in ("id", "title", "difficulty", "pattern", "kind", "status", "reason")} for i in p["items"]]
    return p


def get_upcoming_schedule(days: int = 21) -> list:
    """Mode (exam/normal/free/off) and problem counts for each of the next `days` days."""
    return planner.upcoming_modes(min(max(days, 1), 120))


def set_mode_for_dates(start_date: str, end_date: str, mode: str, note: str = "") -> str:
    """Set the mode for an inclusive date range (YYYY-MM-DD). mode: exam (5-10 min, easy reviews only),
    normal, free (more problems), off (nothing). Later entries override earlier overlapping ones."""
    if mode not in planner.MODES:
        return f"mode must be one of {planner.MODES}"
    s, e = date.fromisoformat(start_date), date.fromisoformat(end_date)
    if e < s:
        return "end_date is before start_date"
    with db.tx() as c:
        c.execute("INSERT INTO availability(start_day, end_day, mode, note) VALUES (?,?,?,?)",
                  (s.isoformat(), e.isoformat(), mode, note or None))
    return f"{mode} set for {s} to {e}"


def clear_dates(start_date: str, end_date: str) -> str:
    """Remove custom modes that overlap the inclusive date range, so those days use the defaults again."""
    with db.tx() as c:
        n = c.execute("DELETE FROM availability WHERE start_day<=? AND end_day>=?", (end_date, start_date)).rowcount
    return f"removed {n} entries"


def set_default_modes(weekday_mode: str, weekend_mode: str) -> str:
    """Default mode for weekdays and weekends when no date range applies."""
    for m in (weekday_mode, weekend_mode):
        if m not in planner.MODES:
            return f"mode must be one of {planner.MODES}"
    db.set_setting("default_mode", weekday_mode)
    db.set_setting("weekend_mode", weekend_mode)
    return "ok"


def set_daily_counts(mode: str, new_problems: int, review_problems: int) -> str:
    """How many new and review problems a day of the given mode gets."""
    if mode not in planner.MODES:
        return f"mode must be one of {planner.MODES}"
    db.set_setting(f"counts_{mode}", [max(0, int(new_problems)), max(0, int(review_problems))])
    return "ok"


def set_goal(goal_total: int, goal_end_date: str) -> str:
    """Goal: number of curated-list problems to finish by goal_end_date (YYYY-MM-DD)."""
    date.fromisoformat(goal_end_date)
    db.set_setting("goal_total", int(goal_total))
    db.set_setting("goal_end", goal_end_date)
    return "ok"


def regenerate_today_plan() -> dict:
    """Rebuild today's plan after changing modes or counts (finished items are kept)."""
    return get_today_plan() if planner.generate_plan(force=True) else {}


def mark_problem(item_id: int, outcome: str) -> str:
    """Mark an item from today's plan. outcome: solved, failed (couldn't solve) or skip (no time)."""
    it = planner.mark_item(int(item_id), outcome)
    return f"{it['title']}: {it['status']}"


TOOLS = [get_status, get_pattern_analysis, get_today_plan, get_upcoming_schedule, set_mode_for_dates,
         clear_dates, set_default_modes, set_daily_counts, set_goal, regenerate_today_plan, mark_problem]


def _system() -> str:
    t = db.today()
    return f"""You are a DSA placement-prep coach for one student. Today is {t.isoformat()} ({t.strftime('%A')}),
timezone {config.TZ.key}.
A deterministic planner picks the actual problems from a curated pattern list using spaced repetition.
Your job: understand the student's schedule (exams, busy days, free days), change settings with the tools,
and explain progress and weak patterns. Never invent problems or stats: call tools to read them.
Modes: exam = 1 quick easy review (5-10 min); normal = default; free = more problems; off = nothing.
After changing modes or counts that affect today, call regenerate_today_plan.
Resolve relative dates ("next week", "from the 3rd") to YYYY-MM-DD yourself. Be brief and concrete."""


def chat(message: str, history: list[dict] | None = None) -> str:
    """Stateless chat: the browser sends prior turns as [{"role": "user"|"model", "text": ...}]."""
    past = [
        types.Content(role=h["role"], parts=[types.Part(text=str(h["text"]))])
        for h in history or [] if h.get("role") in ("user", "model") and h.get("text")
    ]
    chat_session = _gc().chats.create(
        model=config.GEMINI_MODEL,
        config=types.GenerateContentConfig(system_instruction=_system(), tools=TOOLS),
        history=past,
    )
    resp = chat_session.send_message(message)
    return resp.text or "(no response)"


def email_note(plan: dict) -> str:
    """One or two sentences for the top of the daily email."""
    weak = [a for a in planner.pattern_analysis() if a["label"] in ("weak", "developing")][:4]
    prompt = (
        "Write 1-2 short sentences (max 40 words) for the top of a student's daily DSA email. "
        "Mention one concrete weak spot if useful. No greeting, no emojis.\n"
        f"Plan: {json.dumps([{k: i[k] for k in ('title', 'pattern', 'kind', 'difficulty')} for i in plan['items']])}\n"
        f"Mode: {plan['mode']}\nPace: {json.dumps(planner.pace())}\n"
        f"Weak/developing patterns: {json.dumps([{k: a[k] for k in ('pattern', 'coverage', 'fail_rate', 'due_reviews')} for a in weak])}"
    )
    resp = _gc().models.generate_content(model=config.GEMINI_MODEL, contents=prompt)
    return (resp.text or "").strip()
