import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path

from core.statistics import team_form
from core.poisson import analyze
from core.ml_model import _features, _indexed_features
from services import history_import
from database import database, repository


def reference_team_form(matches, team, limit=10):
    selected = [m for m in matches if m["home_team"].casefold() == team.casefold()
                or m["away_team"].casefold() == team.casefold()]
    selected.sort(key=lambda m: m["match_date"], reverse=True)
    selected = selected[:limit]
    gf = ga = points = 0
    form = []
    for match in selected:
        is_home = match["home_team"].casefold() == team.casefold()
        scored = int(match["home_goals"] if is_home else match["away_goals"])
        conceded = int(match["away_goals"] if is_home else match["home_goals"])
        gf += scored
        ga += conceded
        points += 3 if scored > conceded else 1 if scored == conceded else 0
        form.append("W" if scored > conceded else "D" if scored == conceded else "L")
    n = len(selected)
    return {"played": n, "gf": round(gf / n, 2) if n else 0,
            "ga": round(ga / n, 2) if n else 0, "points": points, "form": form}


class PerformancePathTests(unittest.TestCase):
    def setUp(self):
        self.matches = [
            {"match_date": f"2025-{month:02d}-01", "home_team": "A", "away_team": "B",
             "home_goals": month % 4, "away_goals": (month + 1) % 3,
             "ht_home_goals": None, "ht_away_goals": None}
            for month in range(1, 13)
        ]

    def test_team_form_preserves_calculated_values(self):
        for team in ("A", "B", "Missing"):
            for limit in (1, 10, 20):
                self.assertEqual(team_form(self.matches, team, limit),
                                 reference_team_form(self.matches, team, limit))

    def test_analysis_remains_valid_and_deterministic(self):
        first = analyze(self.matches, "A", "B")
        second = analyze(self.matches, "A", "B")
        self.assertEqual(first, second)
        self.assertAlmostEqual(first["home_win"] + first["draw"] + first["away_win"], 1.0)
        self.assertEqual(len(first["scores"]), 8)

    def test_indexed_walk_forward_features_match_previous_calculation(self):
        history = {}
        for idx, match in enumerate(self.matches):
            if idx >= 1:
                self.assertEqual(_indexed_features(history, "A", "B"),
                                 _features(self.matches[:idx], "A", "B"))
            history.setdefault(match["home_team"].casefold(), []).append(match)
            history.setdefault(match["away_team"].casefold(), []).append(match)

    def test_overlapping_import_events_fetch_summary_once(self):
        teams = [{"id": "1", "displayName": "A"}, {"id": "2", "displayName": "B"}]
        event = {"id": "fixture-1", "date": "2025-01-01T12:00Z", "competitions": [{
            "status": {"type": {"completed": True}},
            "competitors": [
                {"homeAway": "home", "team": {"id": "1", "displayName": "A"}, "score": "1"},
                {"homeAway": "away", "team": {"id": "2", "displayName": "B"}, "score": "0"},
            ],
        }]}
        def schedule(_league, _team_id, _count):
            return [event]
        with patch.object(history_import, "_teams", return_value=teams), \
             patch.object(history_import, "_schedule", side_effect=schedule), \
             patch.object(history_import, "_get", return_value={"header": {"id": "fixture-1"}}) as get, \
             patch.object(history_import, "match_identity_rows", return_value=[]), \
             patch.object(history_import, "add_match") as add:
            result = history_import.import_both("eng.1", "A", "B", count=1)
        self.assertEqual(result["added"], 1)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(add.call_count, 1)

    def test_existing_import_match_does_not_fetch_its_unused_summary(self):
        teams = [{"id": "1", "displayName": "A"}, {"id": "2", "displayName": "B"}]
        event = {"id": "fixture-1", "date": "2025-01-01T12:00Z", "competitions": [{
            "status": {"type": {"completed": True}},
            "competitors": [
                {"homeAway": "home", "team": {"id": "1", "displayName": "A"}, "score": "1"},
                {"homeAway": "away", "team": {"id": "2", "displayName": "B"}, "score": "0"},
            ],
        }]}
        with patch.object(history_import, "_teams", return_value=teams), \
             patch.object(history_import, "_schedule", return_value=[event]), \
             patch.object(history_import, "_get") as get, \
             patch.object(history_import, "match_identity_rows", return_value=[
                 {"match_date": "2025-01-01", "home_team": "A", "away_team": "B"}]), \
             patch.object(history_import, "add_match") as add:
            result = history_import.import_both("eng.1", "A", "B", count=1)
        self.assertEqual(result["skipped"], 1)
        get.assert_not_called()
        add.assert_not_called()

    def test_batch_import_keeps_valid_rows_and_reports_invalid_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(database, "DB_PATH", Path(folder) / "test.db"):
                database.initialize()
                rows = [
                    (0, {"match_date": "2025-01-01", "competition": "League", "home_team": "A",
                         "away_team": "B", "home_goals": 1, "away_goals": 0,
                         "ht_home_goals": None, "ht_away_goals": None, "notes": ""}),
                    (1, {"match_date": "bad-date", "competition": "League", "home_team": "C",
                         "away_team": "D", "home_goals": 1, "away_goals": 0,
                         "ht_home_goals": None, "ht_away_goals": None, "notes": ""}),
                    (2, {"match_date": "2025-01-03", "competition": "League", "home_team": "A",
                         "away_team": "C", "home_goals": 2, "away_goals": 2,
                         "ht_home_goals": 1, "ht_away_goals": 1, "notes": ""}),
                ]
                added, errors = repository.add_matches(rows)
                self.assertEqual(added, 2)
                self.assertEqual([index for index, _ in errors], [1])
                self.assertEqual(len(repository.list_matches()), 2)


if __name__ == "__main__":
    unittest.main()
