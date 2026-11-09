import math
from collections import defaultdict
from core.statistics import team_form

def pmf(k, lam):
    if lam < 0:
        return 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def _team_rates(matches, team):
    form = team_form(matches, team, limit=20)
    return form["gf"], form["ga"], form["played"]

def estimate_lambdas(matches, home, away):
    if len(matches) < 4:
        raise ValueError("خاص على الأقل 4 مباريات محفوظة قبل التحليل. الأفضل توفير 20 مباراة أو أكثر.")
    home_rates = _team_rates(matches, home)
    away_rates = _team_rates(matches, away)
    if not home_rates[2] or not away_rates[2]:
        raise ValueError("خاص الفريقين يكون عندهم مباريات سابقة مسجلة.")
    league_home = sum(int(m["home_goals"]) for m in matches) / len(matches)
    league_away = sum(int(m["away_goals"]) for m in matches) / len(matches)
    home_attack = home_rates[0] / max(league_home, 0.25)
    away_defence = away_rates[1] / max(league_home, 0.25)
    away_attack = away_rates[0] / max(league_away, 0.25)
    home_defence = home_rates[1] / max(league_away, 0.25)
    lam_home = max(0.15, league_home * home_attack * away_defence)
    lam_away = max(0.15, league_away * away_attack * home_defence)
    return min(lam_home, 4.5), min(lam_away, 4.5)

def analyze(matches, home, away, max_goals=8):
    lh, la = estimate_lambdas(matches, home, away)
    matrix = [[pmf(i, lh) * pmf(j, la) for j in range(max_goals+1)] for i in range(max_goals+1)]
    total = sum(map(sum, matrix))
    matrix = [[v/total for v in row] for row in matrix]
    p_home = sum(matrix[i][j] for i in range(max_goals+1) for j in range(max_goals+1) if i > j)
    p_draw = sum(matrix[i][j] for i in range(max_goals+1) for j in range(max_goals+1) if i == j)
    p_away = max(0, 1-p_home-p_draw)
    p_over25 = sum(matrix[i][j] for i in range(max_goals+1) for j in range(max_goals+1) if i+j >= 3)
    p_btts = sum(matrix[i][j] for i in range(1,max_goals+1) for j in range(1,max_goals+1))
    scores = sorted([(i,j,matrix[i][j]) for i in range(max_goals+1) for j in range(max_goals+1)],
                    key=lambda x:x[2], reverse=True)[:8]
    return {"lambda_home": lh, "lambda_away": la,
            "home_win": p_home, "draw": p_draw, "away_win": p_away,
            "over_25": p_over25, "under_25": 1-p_over25, "btts": p_btts,
            "scores": scores, "model": "Poisson baseline"}
