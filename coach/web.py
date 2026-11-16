import logging
from datetime import date

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, URLSafeSerializer

from . import config, db, jobs, mailer, planner, tracker

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="DSA Coach")
templates = Jinja2Templates(directory=str(config.ROOT / "templates"))
_auth = URLSafeSerializer(config.SECRET_KEY, salt="login")
PUBLIC = ("/a/", "/login", "/api/cron")


@app.on_event("startup")
def _startup() -> None:
    db.init_schema()
    if config.ENABLE_SCHEDULER:
        jobs.start_scheduler()


@app.middleware("http")
async def _require_login(request: Request, call_next):
    if config.APP_PASSWORD and not request.url.path.startswith(PUBLIC):
        try:
            _auth.loads(request.cookies.get("auth", ""))
        except BadSignature:
            return RedirectResponse("/login", status_code=303)
    return await call_next(request)


def _back(msg: str = "") -> RedirectResponse:
    return RedirectResponse(f"/?msg={msg}" if msg else "/", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


@app.post("/login")
def login(password: str = Form(...)):
    if password != config.APP_PASSWORD:
        return RedirectResponse("/login?bad=1", status_code=303)
    r = RedirectResponse("/", status_code=303)
    r.set_cookie("auth", _auth.dumps("ok"), max_age=60 * 60 * 24 * 180, httponly=True, samesite="lax")
    return r


@app.get("/api/cron")
def cron(request: Request):
    """Called daily by Vercel Cron (vercel.json). Vercel sends the CRON_SECRET as a bearer token."""
    if config.CRON_SECRET and request.headers.get("authorization") != f"Bearer {config.CRON_SECRET}":
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return jobs.daily_run()


def _maybe_sync() -> None:
    """Pull LeetCode solves at most every 20 minutes when the dashboard is opened."""
    if db.now_ts() - int(db.get_setting("last_sync") or 0) < 1200:
        return
    try:
        tracker.sync_recent()
    except Exception as e:  # noqa: BLE001
        logging.warning("sync failed: %s", e)
    db.set_setting("last_sync", db.now_ts())


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, msg: str = ""):
    _maybe_sync()
    plan = planner.generate_plan()
    return templates.TemplateResponse(request, "dashboard.html", {
        "plan": plan, "pace": planner.pace(), "analysis": planner.pattern_analysis(),
        "upcoming": planner.upcoming_modes(14), "msg": msg, "label": mailer.MODE_LABEL,
    })


@app.post("/sync")
def sync():
    try:
        n = tracker.sync_recent()
        return _back(f"Synced: {n} new solve(s) from LeetCode")
    except Exception as e:  # noqa: BLE001
        return _back(f"Sync failed: {e}")


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


@app.post("/item/{item_id}/{action}")
def item_action(item_id: int, action: str):
    planner.mark_item(item_id, action)
    return _back()


@app.get("/a/{token}", response_class=HTMLResponse)
def email_action(request: Request, token: str):
    try:
        item_id, action = mailer.parse_token(token)
        item = planner.mark_item(item_id, action)
        ok = True
    except ValueError:
        item, ok = None, False
    return templates.TemplateResponse(request, "action.html", {"item": item, "ok": ok})


@app.post("/manual")
def manual_solve(slug: str = Form(...), outcome: str = Form("solved")):
    slug = slug.strip().rstrip("/").split("/problems/")[-1].split("/")[0]
    tracker.ensure_problems({slug})
    tracker.record_attempt(slug, db.now_ts(), outcome, "manual")
    return _back(f"Recorded {slug} as {outcome}")


@app.get("/schedule", response_class=HTMLResponse)
def schedule(request: Request):
    with db.tx() as c:
        ranges = [dict(r) for r in c.execute("SELECT * FROM availability ORDER BY start_day")]
        settings = {k: db.get_setting(k, c) for k in
                    ("default_mode", "weekend_mode", "goal_total", "goal_end",
                     "counts_exam", "counts_normal", "counts_free")}
    return templates.TemplateResponse(request, "schedule.html", {
        "ranges": ranges, "settings": settings, "upcoming": planner.upcoming_modes(35),
        "modes": planner.MODES, "label": mailer.MODE_LABEL,
    })


@app.post("/schedule")
def add_range(start_day: date = Form(...), end_day: date = Form(...), mode: str = Form(...), note: str = Form("")):
    with db.tx() as c:
        c.execute("INSERT INTO availability(start_day, end_day, mode, note) VALUES (?,?,?,?)",
                  (start_day.isoformat(), max(start_day, end_day).isoformat(), mode, note or None))
    return RedirectResponse("/schedule", status_code=303)


@app.post("/schedule/{rid}/delete")
def del_range(rid: int):
    with db.tx() as c:
        c.execute("DELETE FROM availability WHERE id=?", (rid,))
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
        for m in ("exam", "normal", "free"):
            if f.get(f"{m}_new") is not None and f.get(f"{m}_review") is not None:
                db.set_setting(f"counts_{m}", [int(f[f"{m}_new"]), int(f[f"{m}_review"])], c)
    return RedirectResponse("/schedule", status_code=303)


@app.get("/history", response_class=HTMLResponse)
def history(request: Request):
    with db.tx() as c:
        rows = [dict(r) for r in c.execute(
            """SELECT a.*, p.title, p.pattern, p.difficulty, p.in_list FROM attempts a
               JOIN problems p ON p.slug=a.slug ORDER BY a.ts DESC LIMIT 300""")]
    for r in rows:
        r["day"] = db.ts_to_date(r["ts"]).isoformat()
    return templates.TemplateResponse(request, "history.html", {"rows": rows})


@app.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request):
    return templates.TemplateResponse(request, "chat.html", {"enabled": bool(config.GEMINI_API_KEY)})


@app.post("/api/chat")
async def chat_api(request: Request):
    from . import assistant

    body = await request.json()
    try:
        history = body.get("history") or []
        return {"reply": assistant.chat(str(body.get("message", ""))[:4000], history[-30:])}
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"reply": f"Error: {e}"}, status_code=500)


