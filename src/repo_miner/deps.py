from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

import requests
import semver

try:  # Python 3.11+
    import tomllib as tomli  # type: ignore
except Exception:  # pragma: no cover
    import tomli  # type: ignore

OSV_QUERY_URL = "https://api.osv.dev/v1/query"
PYPI_BASE = "https://pypi.org/pypi/{name}/json"
REQ_LINE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*(?:==\s*([A-Za-z0-9!+_.\-]+))?.*$")


@dataclass
class PackageInfo:
    name: str
    current_version: Optional[str]
    latest_version: Optional[str]
    is_outdated: bool
    vulnerabilities: List[Dict]

    def to_dict(self) -> Dict:
        return asdict(self)


def _parse_requirements(path: Path) -> List[Dict[str, Optional[str]]]:
    packages: List[Dict[str, Optional[str]]] = []
    if not path.exists():
        return packages
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = REQ_LINE.match(line)
        if not m:
            continue
        name, ver = m.group(1), m.group(2)
        packages.append({"name": name, "version": ver})
    return packages


def _parse_pyproject(path: Path) -> List[Dict[str, Optional[str]]]:
    if not path.exists():
        return []
    data = tomli.loads(path.read_text(encoding="utf-8"))
    reqs: List[str] = []
    # PEP 621 style
    deps = data.get("project", {}).get("dependencies", [])
    if isinstance(deps, list):
        reqs.extend(deps)
    # Poetry
    poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    for k, v in poetry_deps.items():
        if k.lower() == "python":
            continue
        if isinstance(v, str):
            reqs.append(f"{k}=={v}" if re.match(r"^\d", v) else f"{k}{v}")
        elif isinstance(v, dict) and "version" in v:
            reqs.append(f"{k}{v['version']}")
    # Hatch/Flit minimal support via project.dependencies already covered
    pkgs: List[Dict[str, Optional[str]]] = []
    for r in reqs:
        m = REQ_LINE.match(r)
        if not m:
            continue
        pkgs.append({"name": m.group(1), "version": m.group(2)})
    return pkgs


def _latest_pypi_version(name: str) -> Optional[str]:
    url = PYPI_BASE.format(name=name)
    r = requests.get(url, timeout=15)
    if r.status_code != 200:
        return None
    data = r.json()
    # Prefer stable latest version in info.version; fall back scanning releases
    ver = data.get("info", {}).get("version")
    if ver:
        return ver
    releases = data.get("releases", {})
    versions = sorted(
        [v for v in releases.keys() if not _is_prerelease(v)],
        key=_semver_key,
        reverse=True,
    )
    return versions[0] if versions else None


def _is_prerelease(version: str) -> bool:
    s = version.lower()
    return any(tag in s for tag in ["a", "b", "rc", "dev"])


def _semver_key(v: str):  # tolerate non-semver by fallback
    try:
        return semver.Version.parse(v)
    except Exception:
        # try loose parsing: split by dots
        parts = re.split(r"[^0-9]+", v)
        nums = [int(p) for p in parts if p.isdigit()]
        while len(nums) < 3:
            nums.append(0)
        return tuple(nums[:3])


def _osv_query(name: str, version: Optional[str]) -> List[Dict]:
    if not version:
        return []
    payload = {
        "package": {"name": name, "ecosystem": "PyPI"},
        "version": version,
    }
    r = requests.post(OSV_QUERY_URL, data=json.dumps(payload), headers={"Content-Type": "application/json"}, timeout=20)
    if r.status_code != 200:
        return []
    data = r.json()
    vulns = data.get("vulns") or data.get("vulnerabilities") or []
    # Reduce noise
    normalized = []
    for v in vulns:
        normalized.append({
            "id": v.get("id"),
            "summary": v.get("summary"),
            "severity": v.get("severity"),
            "aliases": v.get("aliases"),
            "references": v.get("references"),
        })
    return normalized


def analyze_dependencies(project_path: Path, offline: bool = False) -> Dict:
    """Analisa dependências de um projeto Python.

    Procura por requirements.txt e pyproject.toml no caminho informado.
    Para cada pacote, compara versão com PyPI (se online) e consulta vulnerabilidades (OSV).
    """
    project_path = project_path.resolve()
    reqs = _parse_requirements(project_path / "requirements.txt")
    pyproj = _parse_pyproject(project_path / "pyproject.toml")

    # merge de pacotes por nome (pyproject tem precedência)
    by_name: Dict[str, Dict[str, Optional[str]]] = {}
    for p in reqs + pyproj:
        by_name[p["name"].lower()] = p

    packages: List[PackageInfo] = []
    for key, meta in sorted(by_name.items()):
        name = meta["name"]
        cur = meta.get("version")
        if offline:
            packages.append(PackageInfo(name=name, current_version=cur, latest_version=None, is_outdated=False, vulnerabilities=[]))
            continue
        latest = None
        vulns: List[Dict] = []
        try:
            latest = _latest_pypi_version(name)
        except Exception:
            latest = None
        try:
            vulns = _osv_query(name, cur)
        except Exception:
            vulns = []
        is_outdated = False
        if cur and latest:
            try:
                is_outdated = _semver_key(latest) > _semver_key(cur)
            except Exception:
                is_outdated = latest != cur
        packages.append(PackageInfo(name=name, current_version=cur, latest_version=latest, is_outdated=is_outdated, vulnerabilities=vulns))

    summary = {
        "packages_total": len(packages),
        "outdated_total": sum(1 for p in packages if p.is_outdated),
        "vulnerable_total": sum(1 for p in packages if p.vulnerabilities),
    }

    return {
        "summary": summary,
        "packages": [p.to_dict() for p in packages],
    }
