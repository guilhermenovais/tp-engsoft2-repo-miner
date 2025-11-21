import json
from typer.testing import CliRunner

import repo_miner.cli as cli_mod


def test_cli_deps_remote_clone(monkeypatch, tmp_path):
    clone_dir = tmp_path / "cloned"

    def fake_mkdtemp(prefix="repo_miner_clone_"):
        clone_dir.mkdir()
        return str(clone_dir)

    def fake_run(cmd, check=True, capture_output=True):  # simulate git clone
        (clone_dir / "pyproject.toml").write_text(
            '[project]\nname="x"\nversion="0.0.1"\ndependencies=["requests==2.0.0"]\n',
            encoding="utf-8",
        )
        class R:
            returncode = 0
        return R()

    monkeypatch.setattr(cli_mod.tempfile, "mkdtemp", fake_mkdtemp)
    monkeypatch.setattr(cli_mod.subprocess, "run", fake_run)

    runner = CliRunner()
    out_json = tmp_path / "deps.json"
    result = runner.invoke(cli_mod.app, ["deps", "https://github.com/org/repo", "--offline", "--json-out", str(out_json)])
    assert result.exit_code == 0
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["summary"]["packages_total"] == 1