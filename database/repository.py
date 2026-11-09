from database.database import connection

def _team_id(conn, name, cache=None):
    name = name.strip()
    if not name:
        raise ValueError("اسم الفريق مطلوب")
    cache = cache if cache is not None else {}
    if name.casefold() in cache:
        return cache[name.casefold()]
    conn.execute("INSERT OR IGNORE INTO teams(name) VALUES (?)", (name,))
    value = conn.execute("SELECT id FROM teams WHERE name = ? COLLATE NOCASE", (name,)).fetchone()["id"]
    cache[name.casefold()] = value
    return value

def _competition_id(conn, name, cache=None):
    name = (name or "").strip()
    if not name:
        return None
    cache = cache if cache is not None else {}
    if name.casefold() in cache:
        return cache[name.casefold()]
    conn.execute("INSERT OR IGNORE INTO competitions(name) VALUES (?)", (name,))
    value = conn.execute("SELECT id FROM competitions WHERE name = ? COLLATE NOCASE", (name,)).fetchone()["id"]
    cache[name.casefold()] = value
    return value

def add_match(data):
    validate_match(data)
    with connection() as conn:
        home_id = _team_id(conn, data["home_team"])
        away_id = _team_id(conn, data["away_team"])
        comp_id = _competition_id(conn, data.get("competition"))
        conn.execute("""
            INSERT INTO matches(match_date, competition_id, home_team_id, away_team_id,
              home_goals, away_goals, ht_home_goals, ht_away_goals, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (data["match_date"], comp_id, home_id, away_id, int(data["home_goals"]),
              int(data["away_goals"]), int(data["ht_home_goals"]) if data.get("ht_home_goals") not in (None, "") else None,
              int(data["ht_away_goals"]) if data.get("ht_away_goals") not in (None, "") else None,
              data.get("notes", "")))

def add_matches(rows):
    """Insert valid import rows in one connection while retaining row errors."""
    added, errors = 0, []
    team_cache, competition_cache = {}, {}
    with connection() as conn:
        for index, data in rows:
            conn.execute("SAVEPOINT import_match")
            row_teams, row_competitions = dict(team_cache), dict(competition_cache)
            try:
                validate_match(data)
                home_id = _team_id(conn, data["home_team"], row_teams)
                away_id = _team_id(conn, data["away_team"], row_teams)
                comp_id = _competition_id(conn, data.get("competition"), row_competitions)
                conn.execute("""
                    INSERT INTO matches(match_date, competition_id, home_team_id, away_team_id,
                      home_goals, away_goals, ht_home_goals, ht_away_goals, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (data["match_date"], comp_id, home_id, away_id, int(data["home_goals"]),
                      int(data["away_goals"]), int(data["ht_home_goals"]) if data.get("ht_home_goals") not in (None, "") else None,
                      int(data["ht_away_goals"]) if data.get("ht_away_goals") not in (None, "") else None,
                      data.get("notes", "")))
                conn.execute("RELEASE import_match")
                team_cache.update(row_teams)
                competition_cache.update(row_competitions)
                added += 1
            except Exception as exc:
                conn.execute("ROLLBACK TO import_match")
                conn.execute("RELEASE import_match")
                errors.append((index, exc))
    return added, errors

def validate_match(d):
    from datetime import date
    try:
        date.fromisoformat(d["match_date"])
    except Exception:
        raise ValueError("التاريخ خاصو يكون بصيغة YYYY-MM-DD")
    for key in ("home_goals", "away_goals", "ht_home_goals", "ht_away_goals"):
        if d.get(key) in (None, "") and key.startswith("ht_"):
            continue
        value = int(d[key])
        if value < 0:
            raise ValueError("عدد الأهداف لا يمكن أن يكون سالباً")
    if ((d.get("ht_home_goals") not in (None, "") and int(d["ht_home_goals"]) > int(d["home_goals"])) or
        (d.get("ht_away_goals") not in (None, "") and int(d["ht_away_goals"]) > int(d["away_goals"]))):
        raise ValueError("أهداف الشوط الأول لا يمكن أن تتجاوز أهداف المباراة")
    if not d["home_team"].strip() or not d["away_team"].strip():
        raise ValueError("اسم الفريقين مطلوب")
    if d["home_team"].strip().casefold() == d["away_team"].strip().casefold():
        raise ValueError("الفريق المضيف والضيف لا يمكن أن يكونا نفس الفريق")

def list_matches(limit=5000):
    with connection() as conn:
        rows = conn.execute("""
          SELECT m.id, m.match_date, COALESCE(c.name,'') competition,
            h.name home_team, a.name away_team, m.home_goals, m.away_goals,
            m.ht_home_goals, m.ht_away_goals, m.notes
          FROM matches m JOIN teams h ON h.id=m.home_team_id
          JOIN teams a ON a.id=m.away_team_id
          LEFT JOIN competitions c ON c.id=m.competition_id
          ORDER BY m.match_date DESC, m.id DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]

def match_identity_rows():
    """Return only fields needed for duplicate detection during import."""
    with connection() as conn:
        rows = conn.execute("""
          SELECT m.match_date, h.name home_team, a.name away_team
          FROM matches m JOIN teams h ON h.id=m.home_team_id
          JOIN teams a ON a.id=m.away_team_id
        """).fetchall()
        return rows

def delete_match(match_id):
    with connection() as conn:
        conn.execute("DELETE FROM matches WHERE id=?", (int(match_id),))

def team_names():
    with connection() as conn:
        return [r["name"] for r in conn.execute("SELECT name FROM teams ORDER BY name")]

def save_prediction(home, away, payload, model="Poisson"):
    import json
    with connection() as conn:
        conn.execute("INSERT INTO predictions(home_team,away_team,model_name,payload) VALUES(?,?,?,?)",
                     (home, away, model, json.dumps(payload, ensure_ascii=False)))

def summary():
    with connection() as conn:
        count = conn.execute("SELECT COUNT(*) n FROM matches").fetchone()["n"]
        teams = conn.execute("SELECT COUNT(*) n FROM teams").fetchone()["n"]
        avg = conn.execute("SELECT AVG(home_goals + away_goals) v FROM matches").fetchone()["v"]
        return {"matches": count, "teams": teams, "avg_goals": round(avg or 0, 2)}
