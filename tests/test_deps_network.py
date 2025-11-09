from pathlib import Path
from repo_miner import deps as deps_mod


class DummyResp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json


def test_latest_pypi_version(monkeypatch):
    def fake_get(url, timeout=15):
        return DummyResp(200, {"info": {"version": "1.2.3"}})

    monkeypatch.setattr(deps_mod, "requests", type("R", (), {"get": staticmethod(fake_get)}))
    assert deps_mod._latest_pypi_version("foo") == "1.2.3"


def test_osv_query(monkeypatch):
    def fake_post(url, data=None, headers=None, timeout=20):
        return DummyResp(200, {"vulns": [{"id": "OSV-1", "summary": "x"}]})

    monkeypatch.setattr(deps_mod, "requests", type("R", (), {"post": staticmethod(fake_post)}))
    vulns = deps_mod._osv_query("pkg", "1.0.0")
    assert vulns and vulns[0]["id"] == "OSV-1"


def test_analyze_dependencies_offline(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("a_pkg==1.0.0\n", encoding="utf-8")
    report = deps_mod.analyze_dependencies(tmp_path, offline=True)
    assert report["summary"]["packages_total"] == 1
    assert report["packages"][0]["latest_version"] is None
