"""Daily email via Gmail SMTP (App Password)."""

import html
import smtplib
from datetime import date
from email.message import EmailMessage

from itsdangerous import BadSignature, URLSafeSerializer

from . import config, db, planner

_signer = URLSafeSerializer(config.SECRET_KEY, salt="plan-action")

MODE_LABEL = {"exam": "Exam mode · 5–10 min", "normal": "Normal day", "free": "Free day", "off": "Rest day"}
DIFF_COLOR = {"Easy": "#1a7f37", "Medium": "#b35900", "Hard": "#cf222e"}


def action_url(item_id: int, action: str) -> str:
    return f"{config.BASE_URL}/a/{_signer.dumps({'i': item_id, 'a': action})}"


def parse_token(token: str) -> tuple[int, str]:
    try:
        d = _signer.loads(token)
    except BadSignature as e:
        raise ValueError("invalid link") from e
    return int(d["i"]), d["a"]


def _button(url: str, label: str, bg: str) -> str:
    return (f'<a href="{url}" style="display:inline-block;padding:6px 12px;margin:4px 6px 0 0;border-radius:6px;'
            f'background:{bg};color:#fff;text-decoration:none;font-size:13px">{label}</a>')


def render(plan: dict, note: str | None = None) -> tuple[str, str, str]:
    d = date.fromisoformat(plan["day"])
    items = plan["items"]
    subject = f"DSA {d.strftime('%a %d %b')}: {len(items)} problem{'s' if len(items) != 1 else ''} ({MODE_LABEL[plan['mode']]})"
    p = planner.pace()

    rows_html, rows_txt = [], []
    for i, it in enumerate(items, 1):
        color = DIFF_COLOR.get(it["difficulty"], "#57606a")
        tag = "Review" if it["kind"] == "review" else "New"
        rows_html.append(f"""
        <tr><td style="padding:14px 0;border-bottom:1px solid #eaeef2">
          <div style="font-size:16px;font-weight:600">
            <a href="{it['url']}" style="color:#0969da;text-decoration:none">{i}. {html.escape(it['title'] or it['slug'])}</a>
          </div>
          <div style="font-size:13px;color:#57606a;margin-top:2px">
            <span style="color:{color};font-weight:600">{it['difficulty'] or ''}</span> · {html.escape(it['pattern'])} ·
            <b>{tag}</b>: {html.escape(it['reason'] or '')}
          </div>
          <div>{_button(action_url(it['id'], 'solved'), '✅ Solved', '#1a7f37')}
               {_button(action_url(it['id'], 'failed'), "😵 Couldn't solve", '#b35900')}
               {_button(action_url(it['id'], 'skip'), '⏭ No time', '#57606a')}</div>
        </td></tr>""")
        rows_txt.append(f"{i}. [{tag}] {it['title']} ({it['difficulty']}, {it['pattern']}) - {it['url']}\n   {it['reason']}")

    notes = " ".join(x for x in (plan.get("note"), note) if x)
    pace_line = (f"{p['list_done']}/{p['goal_total']} list problems done · {p['days_left']} days left · "
                 + ("on track" if p["on_track"] else f"{p['shortfall']} behind at current settings")
                 + f" · {p['reviews_due']} reviews due")

    body_html = f"""<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:560px;margin:auto;color:#1f2328">
      <div style="font-size:13px;color:#57606a">{MODE_LABEL[plan['mode']]}</div>
      <h2 style="margin:4px 0 8px">Today's DSA</h2>
      {f'<p style="background:#f6f8fa;padding:10px 12px;border-radius:6px;font-size:14px">{html.escape(notes)}</p>' if notes else ''}
      <table style="width:100%;border-collapse:collapse">{''.join(rows_html)}</table>
      <p style="font-size:13px;color:#57606a;margin-top:16px">{pace_line}</p>
      <p style="font-size:12px;color:#8c959f">Problems you solve on LeetCode are picked up automatically. The buttons are for
      "couldn't solve" and "no time", so tomorrow's plan can adjust. <a href="{config.BASE_URL}/">Open dashboard</a></p>
    </div>"""
    body_txt = f"{MODE_LABEL[plan['mode']]}\n{notes}\n\n" + "\n\n".join(rows_txt) + f"\n\n{pace_line}\n{config.BASE_URL}/"
    return subject, body_txt, body_html


def send(subject: str, text: str, html_body: str) -> None:
    if not (config.GMAIL_ADDRESS and config.GMAIL_APP_PASSWORD):
        raise RuntimeError("GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set in .env")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"DSA Coach <{config.GMAIL_ADDRESS}>"
    msg["To"] = config.MAIL_TO
    msg.set_content(text)
    msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        s.send_message(msg)


def send_plan(plan: dict) -> bool:
    """Email the plan. Returns False when there's nothing to send (rest day)."""
    if not plan["items"]:
        return False
    note = None
    if config.GEMINI_API_KEY:
        try:
            from .assistant import email_note
            note = email_note(plan)
        except Exception:  # noqa: BLE001 - the note is optional
            note = None
    send(*render(plan, note))
    with db.tx() as c:
        c.execute("UPDATE plans SET emailed_at=? WHERE day=?", (db.now_ts(), plan["day"]))
    return True
