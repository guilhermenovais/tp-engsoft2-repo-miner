import json
from pathlib import Path
from typer.testing import CliRunner

from repo_miner.cli import app


runner = CliRunner()


def test_cli_activity_json(tmp_path, monkeypatch):
    def fake_analyze_activity(repo_path: str, since_days: int = 365):
        return {"commits_total": 42, "days_since_last_commit": 1}

    import repo_miner.cli as cli_mod

    monkeypatch.setattr(cli_mod, "analyze_activity", fake_analyze_activity)

    out = tmp_path / "activity.json"
    result = runner.invoke(app, ["activity", str(tmp_path), "--since-days", "30", "--json-out", str(out)])
    assert result.exit_code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["commits_total"] == 42


def test_cli_deps_offline_json_csv(tmp_path, monkeypatch):
    report = {
        "summary": {"packages_total": 2, "outdated_total": 1, "vulnerable_total": 0},
        "packages": [
            {"name": "a", "current_version": "1.0.0", "latest_version": "1.1.0", "is_outdated": True, "vulnerabilities": []},
            {"name": "b", "current_version": None, "latest_version": None, "is_outdated": False, "vulnerabilities": []},
        ],
    }

    import repo_miner.cli as cli_mod

    monkeypatch.setattr(cli_mod, "analyze_dependencies", lambda p, offline=False: report)

    json_path = tmp_path / "deps.json"
    csv_path = tmp_path / "deps.csv"
    result = runner.invoke(app, ["deps", str(tmp_path), "--offline", "--json-out", str(json_path), "--csv-out", str(csv_path)])
    assert result.exit_code == 0
    assert json.loads(json_path.read_text(encoding="utf-8")) == report
    csv_content = csv_path.read_text(encoding="utf-8").splitlines()
    assert len(csv_content) >= 2


def test_cli_analyze_score(tmp_path, monkeypatch):
    import repo_miner.cli as cli_mod

    monkeypatch.setattr(cli_mod, "analyze_activity", lambda repo_path, since_days=365: {"commits_total": 100, "days_since_last_commit": 2})
    monkeypatch.setattr(
        cli_mod,
        "analyze_dependencies",
        lambda p: {"packages": [{"is_outdated": True}, {"is_outdated": False}]},
    )
    result = runner.invoke(app, ["analyze", str(tmp_path)])
    assert result.exit_code == 0
    # result prints JSON to stdout
    data = json.loads(result.stdout)
    assert 0 <= data["maintenance_score"] <= 100
