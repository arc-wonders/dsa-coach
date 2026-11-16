import logging
from datetime import date

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, URLSafeSerializer

from . import config, db, insights, jobs, mailer, planner, tracker
from .patterns import PATTERNS

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="DSA Coach")
app.mount("/static", StaticFiles(directory=str(config.ROOT / "static")), name="static")
templates = Jinja2Templates(directory=str(config.ROOT / "templates"))
templates.env.globals["LEVELS"] = planner.LEVEL_NAMES
_auth = URLSafeSerializer(config.SECRET_KEY, salt="login")
PUBLIC = ("/a/", "/login", "/api/cron", "/static/")


@app.on_event("startup")
def _startup() -> None:
    db.init_schema()
    try:
        with db.tx() as c:
            n = c.execute("SELECT COUNT(*) FROM problems WHERE in_list=1").fetchone()[0]
        if n < sum(len(items) for _, items in PATTERNS):
            tracker.seed_problems()
    except Exception:  # noqa: BLE001
        logging.exception("seeding new problems failed")
    if config.ENABLE_SCHEDULER:
        jobs.start_scheduler()


@app.middleware("http")
async def _require_login(request: Request, call_next):
    if config.APP_PASSWORD and not request.url.path.startswith(PUBLIC):
        try:
            _auth.loads(request.cookies.get("auth", ""))
        except BadSignature:
            if request.url.path.startswith("/api/"):
                return JSONResponse({"error": "login required"}, status_code=401)
            return RedirectResponse("/login", status_code=303)
    return await call_next(request)


def _back(msg: str = "", to: str = "/") -> RedirectResponse:
    return RedirectResponse(f"{to}?msg={msg}" if msg else to, status_code=303)


def _render(request: Request, name: str, ctx: dict):
    return templates.TemplateResponse(request, name, {"page": name.split(".")[0], **ctx})


# ---------------- auth ----------------

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, bad: int = 0):
    return _render(request, "login.html", {"bad": bad})


@app.post("/login")
def login(password: str = Form(...)):
    if password != config.APP_PASSWORD:
        return RedirectResponse("/login?bad=1", status_code=303)
    r = RedirectResponse("/", status_code=303)
    r.set_cookie("auth", _auth.dumps("ok"), max_age=60 * 60 * 24 * 180, httponly=True, samesite="lax")
    return r


# ---------------- cron / sync ----------------

@app.get("/api/cron")
def cron(request: Request):
    """Called daily by Vercel Cron (vercel.json). Vercel sends the CRON_SECRET as a bearer token."""
    if config.CRON_SECRET and request.headers.get("authorization") != f"Bearer {config.CRON_SECRET}":
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return jobs.daily_run()


def _maybe_sync() -> None:
    """Pull LeetCode solves at most every 20 minutes when a page is opened."""
    if db.now_ts() - int(db.get_setting("last_sync") or 0) < 1200:
        return
    try:
        tracker.sync_recent()
    except Exception as e:  # noqa: BLE001
        logging.warning("sync failed: %s", e)
    db.set_setting("last_sync", db.now_ts())


@app.post("/sync")
def sync():
    try:
        n = tracker.sync_recent()
        db.set_setting("last_sync", db.now_ts())
        return _back(f"Synced: {n} new solve(s) from LeetCode")
    except Exception as e:  # noqa: BLE001
        return _back(f"Sync failed: {e}")


# ---------------- pages ----------------

@app.get("/", response_class=HTMLResponse)
def today_page(request: Request, msg: str = ""):
    _maybe_sync()
    plan = planner.generate_plan()
    week = planner.schedule(7)
    data = insights.build()
    return _render(request, "today.html", {
        "plan": plan, "week": week, "pace": data["pace"], "streak": data["streak"], "msg": msg,
        "today": date.fromisoformat(plan["day"]),
    })


@app.get("/insights", response_class=HTMLResponse)
def insights_page(request: Request):
    return _render(request, "insights.html", {"d": insights.build()})


@app.get("/schedule", response_class=HTMLResponse)
def schedule_page(request: Request):
    with db.tx() as c:
        ranges = [dict(r) for r in c.execute("SELECT * FROM availability ORDER BY start_day")]
        settings = {k: db.get_setting(k, c) for k in ("default_mode", "weekend_mode", "goal_total", "goal_end",
                                                       "mode_levels", "level_minutes")}
    return _render(request, "schedule.html", {
        "ranges": ranges, "settings": settings, "modes": planner.MODES, "today": db.today().isoformat(),
        "pace": planner.pace(),
    })


@app.get("/sheet", response_class=HTMLResponse)
def sheet_page(request: Request, f: str = "all"):
    with db.tx() as c:
        rows = [dict(r) for r in c.execute(
            """SELECT p.slug, p.title, p.difficulty, p.pattern, p.list_order, p.striver,
                      COALESCE(s.solves,0) solves, COALESCE(s.fails,0) fails, s.last_solved, s.due
               FROM problems p LEFT JOIN srs s ON s.slug=p.slug WHERE p.in_list=1
               ORDER BY p.list_order""")]
    now = db.now_ts()
    groups = []
    for name, _ in PATTERNS:
        items = [r for r in rows if r["pattern"] == name]
        for r in items:
            r["state"] = ("due" if r["due"] and r["due"] <= now else "solved") if r["solves"] else (
                "failed" if r["fails"] else "todo")
            r["ago"] = (now - r["last_solved"]) // 86400 if r["last_solved"] else None
        shown = [r for r in items if f == "all" or (f == "striver" and r["striver"]) or (f == "todo" and not r["solves"])]
        if shown:
            groups.append({"name": name, "done": sum(1 for r in items if r["solves"]), "total": len(items), "items": shown})
    return _render(request, "sheet.html", {"groups": groups, "f": f,
                                           "counts": {"all": len(rows), "striver": sum(r["striver"] for r in rows),
                                                      "todo": sum(1 for r in rows if not r["solves"])}})


@app.get("/history", response_class=HTMLResponse)
def history_page(request: Request):
    with db.tx() as c:
        rows = [dict(r) for r in c.execute(
            """SELECT a.*, p.title, p.pattern, p.difficulty, p.in_list FROM attempts a
               JOIN problems p ON p.slug=a.slug ORDER BY a.ts DESC LIMIT 300""")]
    for r in rows:
        r["date"] = db.ts_to_date(r["ts"])
    return _render(request, "history.html", {"rows": rows})


@app.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request):
    return _render(request, "chat.html", {"enabled": bool(config.GEMINI_API_KEY)})


# ---------------- plan actions ----------------

@app.post("/regen")
def regen():
    planner.generate_plan(force=True)
    return _back("Today's plan rebuilt")


@app.post("/send")
def send_now():
    try:
        sent = mailer.send_plan(planner.generate_plan())
        return _back("Email sent" if sent else "Nothing to send today")
    except Exception as e:  # noqa: BLE001
        return _back(f"Email failed: {e}")


@app.post("/item/{item_id}/swap")
def item_swap(item_id: int):
    pick = planner.swap_item(item_id)
    return _back("Swapped for something easier" if pick else "Nothing easier available right now")


@app.post("/item/{item_id}/{action}")
def item_action(item_id: int, action: str):
    planner.mark_item(item_id, action)
    return _back()


@app.post("/add")
def add_one():
    pick = planner.add_item()
    return _back("Added one more problem" if pick else "Nothing else to add right now")


@app.get("/a/{token}", response_class=HTMLResponse)
def email_action(request: Request, token: str):
    try:
        item_id, action = mailer.parse_token(token)
        if action == "swap":
            pick = planner.swap_item(item_id)
            item = {"title": "Swapped", "status": "replaced with an easier problem" if pick else "nothing easier available"}
        else:
            item = planner.mark_item(item_id, action)
        ok = True
    except ValueError:
        item, ok = None, False
    return _render(request, "action.html", {"item": item, "ok": ok})


@app.post("/manual")
def manual_solve(slug: str = Form(...), outcome: str = Form("solved")):
    slug = slug.strip().rstrip("/").split("/problems/")[-1].split("/")[0]
    tracker.ensure_problems({slug})
    tracker.record_attempt(slug, db.now_ts(), outcome, "manual")
    return _back(f"Recorded {slug} as {outcome}", "/history")


# ---------------- schedule ----------------

@app.get("/api/schedule")
def api_schedule(days: int = 28):
    return planner.schedule(max(7, min(days, 120)))


@app.post("/api/load")
async def api_load(request: Request):
    body = await request.json()
    changed = []
    for entry in body.get("days", []):
        d = date.fromisoformat(entry["day"])
        if d < db.today():
            continue
        planner.set_day_level(d, entry.get("level"))
        changed.append(d)
    replanned = False
    if db.today() in changed:
        planner.generate_plan(force=True)
        replanned = True
    return {"ok": True, "replanned": replanned, "schedule": planner.schedule(int(body.get("horizon", 28)))}


@app.post("/api/load/reset")
def api_load_reset():
    with db.tx() as c:
        c.execute("DELETE FROM day_load WHERE day>=?", (db.today().isoformat(),))
    planner.generate_plan(force=True)
    return {"ok": True}


@app.post("/schedule")
def add_range(start_day: date = Form(...), end_day: date = Form(...), mode: str = Form(...), note: str = Form("")):
    with db.tx() as c:
        c.execute("INSERT INTO availability(start_day, end_day, mode, note) VALUES (?,?,?,?)",
                  (start_day.isoformat(), max(start_day, end_day).isoformat(), mode, note or None))
    t = db.today().toordinal()
    if start_day.toordinal() <= t + 1 and end_day.toordinal() >= t:
        planner.generate_plan(force=True)  # today is affected (in range, or the block starts tomorrow)
    return RedirectResponse("/schedule", status_code=303)


@app.post("/schedule/{rid}/delete")
def del_range(rid: int):
    with db.tx() as c:
        c.execute("DELETE FROM availability WHERE id=?", (rid,))
    planner.generate_plan(force=True)
    return RedirectResponse("/schedule", status_code=303)


@app.post("/settings")
async def save_settings(request: Request):
    f = await request.form()
    with db.tx() as c:
        for k in ("default_mode", "weekend_mode", "goal_end"):
            if f.get(k):
                db.set_setting(k, f[k], c)
        if f.get("goal_total"):
            db.set_setting("goal_total", int(f["goal_total"]), c)
        levels = db.get_setting("mode_levels", c)
        for m in planner.MODES:
            if f.get(f"level_{m}") is not None:
                levels[m] = max(0, min(4, int(f[f"level_{m}"])))
        db.set_setting("mode_levels", levels, c)
        minutes = db.get_setting("level_minutes", c)
        for i in range(1, 5):
            if f.get(f"min_{i}"):
                minutes[i] = max(5, min(300, int(f[f"min_{i}"])))
        db.set_setting("level_minutes", minutes, c)
    planner.generate_plan(force=True)
    return RedirectResponse("/schedule?saved=1", status_code=303)


# ---------------- assistant ----------------

@app.post("/api/chat")
async def chat_api(request: Request):
    from . import assistant

    body = await request.json()
    try:
        history = body.get("history") or []
        return {"reply": assistant.chat(str(body.get("message", ""))[:4000], history[-30:])}
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"reply": f"Error: {e}"}, status_code=500)
