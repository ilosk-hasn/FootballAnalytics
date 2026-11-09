import pandas as pd

def team_form(matches, team, limit=10):
    df = pd.DataFrame(matches)
    if df.empty:
        return {"played": 0, "gf": 0, "ga": 0, "points": 0, "form": []}
    df = df[(df.home_team.str.casefold() == team.casefold()) |
            (df.away_team.str.casefold() == team.casefold())].sort_values("match_date", ascending=False).head(limit)
    gf = ga = points = 0
    form = []
    for _, m in df.iterrows():
        home = m.home_team.casefold() == team.casefold()
        scored = int(m.home_goals if home else m.away_goals)
        conceded = int(m.away_goals if home else m.home_goals)
        gf += scored; ga += conceded
        points += 3 if scored > conceded else 1 if scored == conceded else 0
        form.append("W" if scored > conceded else "D" if scored == conceded else "L")
    n = len(df)
    return {"played": n, "gf": round(gf/n, 2) if n else 0,
            "ga": round(ga/n, 2) if n else 0, "points": points, "form": form}
