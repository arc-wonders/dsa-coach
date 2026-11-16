"""LeetCode access. There is no official API; this uses the same endpoints the
website uses. Everything LeetCode-specific lives in this file."""

import time

import httpx

from . import config

BASE = "https://leetcode.com"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


class LeetCodeError(RuntimeError):
    pass


def _client(auth: bool = False) -> httpx.Client:
    headers = {"User-Agent": UA, "Referer": BASE + "/", "Content-Type": "application/json"}
    cookies = {}
    if auth:
        if not (config.LEETCODE_SESSION and config.LEETCODE_CSRF):
            raise LeetCodeError("LEETCODE_SESSION and LEETCODE_CSRFTOKEN must be set in .env for a full import")
        cookies = {"LEETCODE_SESSION": config.LEETCODE_SESSION, "csrftoken": config.LEETCODE_CSRF}
        headers["x-csrftoken"] = config.LEETCODE_CSRF
    return httpx.Client(headers=headers, cookies=cookies, timeout=30, follow_redirects=True)


def _gql(client: httpx.Client, query: str, variables: dict) -> dict:
    for attempt in range(3):
        r = client.post(BASE + "/graphql", json={"query": query, "variables": variables})
        if r.status_code == 429:
            time.sleep(5 * (attempt + 1))
            continue
        r.raise_for_status()
        body = r.json()
        if body.get("errors"):
            raise LeetCodeError(str(body["errors"]))
        return body["data"]
    raise LeetCodeError("rate limited by LeetCode")


# ---------- public (no login) ----------

def recent_accepted(username: str | None = None, limit: int = 20) -> list[dict]:
    """Last ~20 accepted submissions. Public; LeetCode caps this at 20."""
    q = """query($u: String!, $n: Int!) {
      recentAcSubmissionList(username: $u, limit: $n) { titleSlug title timestamp }
    }"""
    with _client() as c:
        data = _gql(c, q, {"u": username or config.LEETCODE_USERNAME, "n": limit})
    return [
        {"slug": s["titleSlug"], "title": s["title"], "ts": int(s["timestamp"])}
        for s in data["recentAcSubmissionList"] or []
    ]


def profile_stats(username: str | None = None) -> dict:
    q = """query($u: String!) { matchedUser(username: $u) {
      submitStatsGlobal { acSubmissionNum { difficulty count } } } }"""
    with _client() as c:
        data = _gql(c, q, {"u": username or config.LEETCODE_USERNAME})
    if not data["matchedUser"]:
        raise LeetCodeError("LeetCode user not found")
    return {d["difficulty"]: d["count"] for d in data["matchedUser"]["submitStatsGlobal"]["acSubmissionNum"]}


def question_meta(slugs: list[str], delay: float = 0.25) -> dict[str, dict]:
    """Title, difficulty and topic tags for each slug. Missing slugs are omitted."""
    q = """query($s: String!) { question(titleSlug: $s) {
      titleSlug title difficulty isPaidOnly topicTags { name } } }"""
    out: dict[str, dict] = {}
    with _client() as c:
        for slug in slugs:
            data = _gql(c, q, {"s": slug})
            qd = data.get("question")
            if qd:
                out[slug] = {
                    "title": qd["title"],
                    "difficulty": qd["difficulty"],
                    "paid": qd["isPaidOnly"],
                    "tags": [t["name"] for t in qd["topicTags"]],
                }
            time.sleep(delay)
    return out


# ---------- authenticated (needs session cookie) ----------

def all_submissions(max_pages: int = 200) -> list[dict]:
    """Full submission history (accepted and not) with timestamps.

    Returns dicts: slug, title, ts, accepted(bool).
    """
    out: list[dict] = []
    with _client(auth=True) as c:
        offset, lastkey = 0, ""
        for _ in range(max_pages):
            r = c.get(BASE + "/api/submissions/", params={"offset": offset, "limit": 20, "lastkey": lastkey})
            if r.status_code == 429:
                time.sleep(10)
                continue
            if r.status_code in (401, 403):
                raise LeetCodeError("LeetCode rejected the session cookie (expired?). Copy a fresh one.")
            r.raise_for_status()
            body = r.json()
            for s in body.get("submissions_dump", []):
                out.append({
                    "slug": s["title_slug"],
                    "title": s.get("title"),
                    "ts": int(s["timestamp"]),
                    "accepted": s.get("status_display") == "Accepted",
                })
            if not body.get("has_next"):
                break
            offset += 20
            lastkey = body.get("last_key", "")
            time.sleep(1.5)
    return out


def all_solved_slugs() -> set[str]:
    """Every problem marked accepted on your account (no timestamps)."""
    with _client(auth=True) as c:
        r = c.get(BASE + "/api/problems/all/")
        r.raise_for_status()
        body = r.json()
    if not body.get("user_name"):
        raise LeetCodeError("Not logged in: session cookie invalid or expired")
    return {p["stat"]["question__title_slug"] for p in body["stat_status_pairs"] if p.get("status") == "ac"}
