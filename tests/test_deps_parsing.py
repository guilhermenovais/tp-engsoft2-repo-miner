from pathlib import Path
from textwrap import dedent

from repo_miner import deps as deps_mod


def test_parse_requirements(tmp_path: Path):
    content = dedent(
        """
        # comment
        requests==2.31.0
        numpy==1.26.4  # trailing
        invalid line here
        pandas
        """
    )
    (tmp_path / "requirements.txt").write_text(content, encoding="utf-8")
    pkgs = deps_mod._parse_requirements(tmp_path / "requirements.txt")
    names = [p["name"] for p in pkgs]
    assert "requests" in names
    assert "numpy" in names
    assert "pandas" in names


def test_parse_pyproject(tmp_path: Path):
    py = dedent(
        """
        [project]
        name = "x"
        version = "0.0.1"
        dependencies = [
          "flask==3.0.0",
          "uvicorn>=0.20.0",
        ]

        [tool.poetry]
        name = "x"
        version = "0.0.1"

        [tool.poetry.dependencies]
        python = ">=3.9"
        requests = "2.31.0"
        """
    )
    (tmp_path / "pyproject.toml").write_text(py, encoding="utf-8")
    pkgs = deps_mod._parse_pyproject(tmp_path / "pyproject.toml")
    names = {p["name"] for p in pkgs}
    assert {"flask", "uvicorn", "requests"}.issubset(names)
