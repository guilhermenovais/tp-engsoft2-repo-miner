from pathlib import Path
import json
from repo_miner.exporters import export_json, export_csv


def test_export_json_and_csv(tmp_path: Path):
    data = {"a": 1, "b": 2}
    json_path = tmp_path / "out.json"
    csv_path = tmp_path / "out.csv"

    export_json(data, json_path)
    assert json_path.exists()
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded == data

    rows = [{"name": "x", "val": 1}, {"name": "y", "extra": "z"}]
    export_csv(rows, csv_path)
    content = csv_path.read_text(encoding="utf-8").strip().splitlines()
    # header + 2 rows
    assert len(content) == 3
    assert "name" in content[0] and "val" in content[0] and "extra" in content[0]

def test_export_csv_empty(tmp_path):
    """export_csv deve criar um arquivo vazio quando receber uma lista vazia."""

    from repo_miner.exporters import export_csv

    out = tmp_path / "empty.csv"
    export_csv([], out)

    assert out.exists()

    content = out.read_text(encoding="utf-8")
    assert content == ""
