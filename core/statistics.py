def team_form(matches, team, limit=10):
    """Calculate recent form without building a DataFrame for every team lookup."""
    team_key = team.casefold()
    selected = []
    for position, match in enumerate(matches):
        home = match["home_team"].casefold() == team_key
        away = match["away_team"].casefold() == team_key
        if home or away:
            selected.append((match["match_date"], position, match, home))
    if not selected:
        return {"played": 0, "gf": 0, "ga": 0, "points": 0, "form": []}
    selected.sort(key=lambda item: item[0], reverse=True)
    selected = selected[:limit]
    gf = ga = points = 0
    form = []
    for _, _, m, home in selected:
        scored = int(m["home_goals"] if home else m["away_goals"])
        conceded = int(m["away_goals"] if home else m["home_goals"])
        gf += scored; ga += conceded
        points += 3 if scored > conceded else 1 if scored == conceded else 0
        form.append("W" if scored > conceded else "D" if scored == conceded else "L")
    n = len(selected)
    return {"played": n, "gf": round(gf/n, 2) if n else 0,
            "ga": round(ga/n, 2) if n else 0, "points": points, "form": form}
