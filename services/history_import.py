"""Historical match import from ESPN's public soccer endpoints.

ESPN coverage varies by competition. Missing values are kept as null/empty and
the response fragment is retained in notes so the user can inspect provenance.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from database.repository import add_match, match_identity_rows

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}"
USER_AGENT = "FootballAnalytics/2.0 (historical match importer)"


class ImportErrorWithContext(Exception):
    pass


def _get(url):
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=18) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ImportErrorWithContext(f"استجاب المصدر برمز HTTP {exc.code} للرابط: {url}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ImportErrorWithContext(f"تعذر الاتصال بمصدر ESPN أو قراءة رده: {exc}") from exc


def _norm(value):
    return re.sub(r"[^\w]", "", str(value or "").casefold())


def _teams(league):
    data = _get(BASE.format(league=league) + "/teams?limit=500")
    result = []
    def walk(node):
        if isinstance(node, dict):
            if node.get("id") and node.get("displayName"):
                result.append(node)
            for value in node.values(): walk(value)
        elif isinstance(node, list):
            for value in node: walk(value)
    walk(data.get("sports", data))
    unique = {str(t["id"]): t for t in result}
    return list(unique.values())


def resolve_team(teams, name):
    term = _norm(name)
    matches = [t for t in teams if term in {_norm(t.get(k)) for k in ("displayName", "name", "shortDisplayName", "abbreviation")}]
    if not matches:
        matches = [t for t in teams if any(_norm(t.get(k)).startswith(term) for k in ("displayName", "name", "shortDisplayName"))]
    if not matches:
        raise ImportErrorWithContext(f"لم أجد الفريق «{name}» في مسابقة ESPN المحددة. تحقق من رمز المسابقة والاسم.")
    if len(matches) > 1:
        options = ", ".join(t.get("displayName", "") for t in matches[:8])
        raise ImportErrorWithContext(f"اسم الفريق «{name}» غير محدد. أسماء متقاربة: {options}")
    return matches[0]


def _score(comp, team_id):
    for side in comp.get("competitors", []):
        if str(side.get("team", {}).get("id")) == str(team_id):
            score = side.get("score")
            try:
                return int(float(score)) if score not in (None, "") else None
            except (TypeError, ValueError):
                return None
    return None


def _ht_score(comp, team_id):
    # Score-by-period is not returned consistently for soccer; only use an
    # explicit first-period score supplied by the endpoint.
    lines = comp.get("linescores") or []
    for side in comp.get("competitors", []):
        if str(side.get("team", {}).get("id")) != str(team_id):
            continue
        periods = side.get("linescores") or lines
        if periods and isinstance(periods[0], dict):
            val = periods[0].get("value", periods[0].get("displayValue"))
            try: return int(float(val))
            except (TypeError, ValueError): pass
    return None


def _summary_fields(summary):
    """Extract only explicitly labelled summary facts; preserve unknowns."""
    facts = {"source": "ESPN public soccer summary", "source_url": summary.get("link", "")}
    box = summary.get("boxscore") or {}
    # Keep raw, source-returned match detail (including formations, cards,
    # rosters, injuries, and team/player statistics when ESPN provides them).
    if box: facts["boxscore"] = box
    for key in ("header", "rosters", "injuries", "leaders", "plays"):
        if summary.get(key): facts[key] = summary[key]
    teams = box.get("players") or []
    stats = []
    for team_block in teams:
        team = team_block.get("team", {}).get("displayName")
        for group in team_block.get("statistics", []):
            names = group.get("names", [])
            for athlete in group.get("athletes", []):
                stats.append({"team": team, "player": athlete.get("athlete", {}).get("displayName"),
                              "stats": dict(zip(names, athlete.get("stats", [])))})
    if stats: facts["player_statistics"] = stats
    for key in ("statistics", "rosters", "injuries", "plays", "leaders"):
        value = box.get(key, summary.get(key))
        if value: facts[key] = value
    return facts


def _event_record(event, team_id, league, summaries=True):
    comp = (event.get("competitions") or [{}])[0]
    competitors = comp.get("competitors", [])
    home = next((c for c in competitors if c.get("homeAway") == "home"), None)
    away = next((c for c in competitors if c.get("homeAway") == "away"), None)
    if not home or not away: return None
    hg, ag = _score(comp, home.get("team", {}).get("id")), _score(comp, away.get("team", {}).get("id"))
    status = (comp.get("status") or event.get("status") or {}).get("type", {}).get("completed")
    if not status or hg is None or ag is None: return None
    dt = (event.get("date") or "")[:10]
    try: date.fromisoformat(dt)
    except ValueError: return None
    facts = {"source": "ESPN public soccer scoreboard", "event_id": event.get("id"),
             "source_url": f"https://www.espn.com/soccer/match/_/gameId/{event.get('id')}"}
    if summaries:
        try:
            report = _get(BASE.format(league=league) + "/summary?" + urlencode({"event": event.get("id")}))
            facts.update(_summary_fields(report))
        except Exception as exc:
            facts["summary_error"] = str(exc)
    return {"match_date": dt,
            "competition": league,
            "home_team": home.get("team", {}).get("displayName", ""),
            "away_team": away.get("team", {}).get("displayName", ""),
            "home_goals": hg, "away_goals": ag,
            "ht_home_goals": _ht_score(comp, home.get("team", {}).get("id")),
            "ht_away_goals": _ht_score(comp, away.get("team", {}).get("id")),
            "notes": json.dumps(facts, ensure_ascii=False)}


def _schedule(league, team_id, count):
    data = _get(BASE.format(league=league) + f"/teams/{team_id}/schedule")
    events = data.get("events", [])
    events.sort(key=lambda e: e.get("date", ""), reverse=True)
    return events[:max(count * 5, count)]


def import_both(league, home_name, away_name, count=20, progress=None):
    """Import up to count previous matches for each selected team (mode=both).

    Unique matches are saved once. Existing same fixture/date entries are skipped.
    """
    league = (league or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", league):
        raise ImportErrorWithContext("رمز المسابقة غير صالح؛ مثال: eng.1 أو esp.1")
    if not home_name.strip() or not away_name.strip() or _norm(home_name) == _norm(away_name):
        raise ImportErrorWithContext("أدخل اسمين مختلفين للفريقين.")
    if not 1 <= int(count) <= 20:
        raise ImportErrorWithContext("عدد المباريات يجب أن يكون بين 1 و20 لكل فريق.")
    teams = _teams(league)
    home, away = resolve_team(teams, home_name), resolve_team(teams, away_name)
    candidates = {}
    errors = []
    for team, label in ((home, home_name), (away, away_name)):
        try:
            events = _schedule(league, team["id"], count)
            found = 0
            for event in events:
                # Build the scoreboard record first; summary calls are deferred
                # until overlapping team schedules have been deduplicated.
                record = _event_record(event, team["id"], league, summaries=False)
                if record:
                    candidates[event.get("id")] = record
                    found += 1
                    if found >= count: break
            if progress: progress(f"{label}: عُثر على {found} من {count} مباراة مطلوبة")
            if found < count: errors.append(f"{label}: المتاح {found} من {count} مباراة في سجل المصدر.")
        except Exception as exc:
            errors.append(f"{label}: {exc}")
    # Fetch each event summary once, with bounded concurrency. The old loop made
    # up to 40 serial HTTP calls (each with an 18s timeout) for 40 fixtures.
    existing = {(m["match_date"], _norm(m["home_team"]), _norm(m["away_team"]))
                for m in match_identity_rows()}
    pending_summaries = [event_id for event_id, record in candidates.items()
                         if (record["match_date"], _norm(record["home_team"]), _norm(record["away_team"]))
                         not in existing]
    summary_url = BASE.format(league=league) + "/summary?"
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_get, summary_url + urlencode({"event": event_id})): event_id
                   for event_id in pending_summaries}
        for future in as_completed(futures):
            event_id = futures[future]
            try:
                candidates[event_id]["notes"] = json.dumps(
                    _summary_fields(future.result()), ensure_ascii=False)
            except Exception as exc:
                facts = json.loads(candidates[event_id]["notes"])
                facts["summary_error"] = str(exc)
                candidates[event_id]["notes"] = json.dumps(facts, ensure_ascii=False)

    added, skipped = 0, 0
    for record in sorted(candidates.values(), key=lambda x: x["match_date"], reverse=True):
        key = (record["match_date"], _norm(record["home_team"]), _norm(record["away_team"]))
        if key in existing:
            skipped += 1; continue
        try:
            add_match(record); added += 1; existing.add(key)
        except Exception as exc:
            errors.append(f"{record['match_date']} {record['home_team']} - {record['away_team']}: {exc}")
    return {"added": added, "skipped": skipped, "found": len(candidates), "errors": errors,
            "team_names": (home["displayName"], away["displayName"]), "mode": "both", "requested_per_team": int(count)}
