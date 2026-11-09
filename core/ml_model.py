"""Optional ML layer. Trains only on historical team-form features.
It is deliberately conservative: too little data => no ML probability."""
try:
    from sklearn.ensemble import RandomForestClassifier
except Exception:
    RandomForestClassifier = None

def _features(matches, home, away, before_date=None):
    from core.statistics import team_form
    eligible = matches
    if before_date:
        eligible = [m for m in matches if m["match_date"] < before_date]
    h = team_form(eligible, home, 10)
    a = team_form(eligible, away, 10)
    if not h["played"] or not a["played"]:
        return None
    return [h["gf"], h["ga"], a["gf"], a["ga"], h["points"]/h["played"], a["points"]/a["played"]]

def train_and_predict(matches, home, away):
    if RandomForestClassifier is None or len(matches) < 60:
        return {"available": False, "reason": "يلزم تثبيت scikit-learn وتوفير 60 مباراة على الأقل."}
    X, y = [], []
    ordered = sorted(matches, key=lambda m:m["match_date"])
    for idx, m in enumerate(ordered):
        past = ordered[:idx]
        if len(past) < 10:
            continue
        feat = _features(past, m["home_team"], m["away_team"])
        if feat is None:
            continue
        result = 0 if m["home_goals"] > m["away_goals"] else 1 if m["home_goals"] == m["away_goals"] else 2
        X.append(feat); y.append(result)
    if len(X) < 30 or len(set(y)) < 2:
        return {"available": False, "reason": "المباريات المتاحة غير كافية لتدريب نموذج موثوق."}
    target = _features(matches, home, away)
    if target is None:
        return {"available": False, "reason": "الفريقان يحتاجان إلى سجل سابق."}
    model = RandomForestClassifier(n_estimators=250, max_depth=5, min_samples_leaf=3,
                                   class_weight="balanced", random_state=42)
    model.fit(X, y)
    raw = model.predict_proba([target])[0]
    probs = {int(c):float(p) for c,p in zip(model.classes_, raw)}
    return {"available": True, "probabilities": {
        "home_win": probs.get(0,0), "draw": probs.get(1,0), "away_win": probs.get(2,0)},
        "warning": "نتيجة تجريبية داخل العينة؛ يلزم اختبار زمني خارج العينة ومعايرة قبل الاعتماد."}
