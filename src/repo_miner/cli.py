import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .activity import analyze_activity
from .deps import analyze_dependencies
import subprocess
import tempfile
from urllib.parse import urlparse
from .exporters import export_json, export_csv

app = typer.Typer(help="Ferramenta CLI para minerar repositórios e avaliar saúde de manutenção")
console = Console()


@app.command()
def activity(
    repo: str = typer.Argument(..., help="Caminho local do repositório Git (ou URL clonada previamente)"),
    since_days: int = typer.Option(365, help="Janela de análise em dias"),
    json_out: Optional[Path] = typer.Option(None, help="Arquivo para salvar JSON"),
):
    """Analisa a atividade de commits/merges do repositório."""
    metrics = analyze_activity(repo_path=repo, since_days=since_days)

    if json_out:
        export_json(metrics, json_out)
        console.print(f"JSON salvo em {json_out}")
        return

    # Tabela amigável
    table = Table(title="Atividade do Repositório")
    table.add_column("Métrica")
    table.add_column("Valor")
    for k, v in metrics.items():
        table.add_row(k, str(v))
    console.print(table)


@app.command()
def deps(
    repo: str = typer.Argument(".", help="Caminho local ou URL https://github.com/org/repo para detecção de dependências"),
    json_out: Optional[Path] = typer.Option(None, help="Arquivo para salvar JSON"),
    csv_out: Optional[Path] = typer.Option(None, help="Arquivo para salvar CSV"),
    offline: bool = typer.Option(False, help="Não consultar rede (apenas parse)"),
    auto_clone: bool = typer.Option(True, help="Clonar automaticamente URL remota (depth=1) se caminho for HTTP(S)")
):
    """Analisa dependências: desatualizadas e vulnerabilidades (OSV)."""
    target_path = Path(repo)
    if repo.startswith("http://") or repo.startswith("https://"):
        if not auto_clone:
            console.print("URL remota detectada. Use --auto-clone ou forneça caminho local previamente clonado.", style="red")
            raise typer.Exit(code=1)
        parsed = urlparse(repo)
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) < 2:
            console.print("URL não representa repositório (faltando segmento de projeto). Use formato https://github.com/org/repo", style="red")
            raise typer.Exit(code=1)
        tmpdir = Path(tempfile.mkdtemp(prefix="repo_miner_clone_"))
        console.print(f"Clonando repositório em {tmpdir} ...")
        try:
            subprocess.run(["git", "clone", "--depth", "1", repo, str(tmpdir)], check=True, capture_output=True)
        except Exception as e:
            console.print(f"Falha ao clonar: {e}", style="red")
            raise typer.Exit(code=1)
        target_path = tmpdir
    report = analyze_dependencies(target_path, offline=offline)
    # aviso se nenhum manifesto encontrado
    if report.get("summary", {}).get("packages_total") == 0:
        report["warning"] = "Nenhum arquivo requirements.txt ou pyproject.toml encontrado no caminho informado." 

    if json_out:
        export_json(report, json_out)
        console.print(f"JSON salvo em {json_out}")
    if csv_out:
        export_csv(report.get("packages", []), csv_out)
        console.print(f"CSV salvo em {csv_out}")

    if not (json_out or csv_out):
        console.print(json.dumps(report, indent=2, ensure_ascii=False))


@app.command()
def analyze(
    repo: str = typer.Argument(".", help="Caminho do repositório/projeto"),
    since_days: int = typer.Option(365, help="Janela de atividade (dias)"),
    json_out: Optional[Path] = typer.Option(None, help="Arquivo para salvar JSON"),
):
    """Executa análise combinada (atividade + dependências) e fornece um score simples."""
    activity = analyze_activity(repo_path=repo, since_days=since_days)
    deps = analyze_dependencies(Path(repo))

    # Score simples: 0-100 baseado em atividade e desatualização
    commits = activity.get("commits_total", 0)
    days_since_last = activity.get("days_since_last_commit", 9999)
    outdated = sum(1 for p in deps.get("packages", []) if p.get("is_outdated"))

    score = 50
    score += min(30, commits // 10)
    score += max(0, 20 - min(20, days_since_last))
    score -= min(30, outdated * 5)
    score = max(0, min(100, score))

    result = {
        "activity": activity,
        "dependencies": deps,
        "maintenance_score": score,
    }

    if json_out:
        export_json(result, json_out)
        console.print(f"JSON salvo em {json_out}")
    else:
        console.print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    app() 
