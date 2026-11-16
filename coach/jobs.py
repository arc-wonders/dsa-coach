import logging
import threading
import time
from datetime import datetime

from . import config, db, mailer, planner, tracker

log = logging.getLogger(__name__)


def daily_run(send_email: bool = True) -> dict:
    """Sync LeetCode, build today's plan, email it."""
    result = {"synced": None, "emailed": False}
    try:
        result["synced"] = tracker.sync_recent()
    except Exception as e:  # noqa: BLE001 - still send a plan if LeetCode is down
        log.warning("LeetCode sync failed: %s", e)
        result["sync_error"] = str(e)
    plan = planner.generate_plan()
    result["plan"] = {"mode": plan["mode"], "items": len(plan["items"])}
    if send_email and not plan["emailed_at"]:
        result["emailed"] = mailer.send_plan(plan)
    db.set_setting("last_auto_run", db.today().isoformat())
    return result


def _loop() -> None:
    hh, mm = map(int, config.DAILY_SEND_TIME.split(":"))
    while True:
        try:
            now = datetime.now(config.TZ)
            if (now.hour, now.minute) >= (hh, mm) and db.get_setting("last_auto_run") != now.date().isoformat():
                log.info("daily run: %s", daily_run())
            elif now.minute % 30 == 0:
                tracker.sync_recent()  # keep plan statuses fresh during the day
        except Exception:  # noqa: BLE001
            log.exception("scheduler tick failed")
        time.sleep(60)


def start_scheduler() -> None:
    threading.Thread(target=_loop, daemon=True, name="daily-scheduler").start()
