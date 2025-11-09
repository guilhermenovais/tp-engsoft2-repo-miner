import csv
import json
from pathlib import Path
from typing import Any, Iterable, List


def export_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def export_csv(rows: Iterable[dict], path: Path) -> None:
    rows_list: List[dict] = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows_list:
        path.write_text("", encoding="utf-8")
        return
    # union of keys across rows for consistent columns
    headers = set()
    for r in rows_list:
        headers.update(r.keys())
    headers = sorted(headers)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for r in rows_list:
            writer.writerow(r)
