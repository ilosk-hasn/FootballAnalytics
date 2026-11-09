import pandas as pd
from database.repository import add_matches

COLUMNS = ["match_date","competition","home_team","away_team","home_goals","away_goals","ht_home_goals","ht_away_goals","notes"]

def export_file(path, matches):
    df = pd.DataFrame(matches)
    if "id" in df.columns:
        df = df.drop(columns=["id"])
    df = df[[c for c in COLUMNS if c in df.columns]]
    if str(path).lower().endswith(".csv"):
        df.to_csv(path, index=False, encoding="utf-8-sig")
    else:
        df.to_excel(path, index=False)

def import_file(path):
    df = pd.read_csv(path) if str(path).lower().endswith(".csv") else pd.read_excel(path)
    missing = [c for c in COLUMNS[:-1] if c not in df.columns]
    if missing:
        raise ValueError("أعمدة ناقصة: " + ", ".join(missing))
    rows, errors = [], []
    for idx, row in enumerate(df.to_dict(orient="records")):
        try:
            data = {c: ("" if c not in df.columns or pd.isna(row.get(c)) else row.get(c)) for c in COLUMNS}
            for c in ("home_goals","away_goals","ht_home_goals","ht_away_goals"):
                data[c] = None if c.startswith("ht_") and data[c] == "" else int(data[c])
            data["match_date"] = str(data["match_date"])[:10]
            for c in ("competition","home_team","away_team","notes"):
                data[c] = str(data[c])
            rows.append((idx, data))
        except Exception as exc:
            errors.append((idx, f"السطر {idx+2}: {exc}"))
    added, insert_errors = add_matches(rows)
    errors.extend((idx, f"السطر {idx+2}: {exc}") for idx, exc in insert_errors)
    errors = [message for _, message in sorted(errors, key=lambda item: item[0])]
    return added, errors
