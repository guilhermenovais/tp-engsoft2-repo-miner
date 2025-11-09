from datetime import datetime, timedelta, timezone
from typing import Dict

try:
    # PyDriller < 2.0
    from pydriller import RepositoryMining
except ImportError:  # pragma: no cover - exercised in envs with newer PyDriller
    # PyDriller >= 2.0 renamed RepositoryMining -> Repository with same traverse_commits API
    from pydriller import Repository as RepositoryMining


def analyze_activity(repo_path: str, since_days: int = 365) -> Dict[str, int]:
    """
    Coleta métricas simples de atividade do repositório usando PyDriller.

    - commits_total: total de commits na janela
    - commits_per_author: número de autores distintos
    - days_since_last_commit: dias desde o último commit (0 se hoje)
    - median_days_between_commits: mediana dos intervalos entre commits
    - merge_commits: número de merges (mensagem contém 'Merge' ou múltiplos pais)
    """
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=since_days)

    commit_dates = []
    authors = set()
    merge_commits = 0

    for commit in RepositoryMining(path_to_repo=repo_path, since=since, to=now).traverse_commits():
        # PyDriller normaliza timezone; garantir tz-aware
        cdate = commit.committer_date
        if cdate.tzinfo is None:
            cdate = cdate.replace(tzinfo=timezone.utc)
        commit_dates.append(cdate)
        authors.add(commit.author.email or commit.author.name)
        if getattr(commit, "merge", False) or (getattr(commit, "parents", None) and len(commit.parents) > 1):
            merge_commits += 1
        elif "merge" in (commit.msg or "").lower():
            merge_commits += 1

    commit_dates.sort()
    commits_total = len(commit_dates)
    commits_per_author = len(authors)

    if commit_dates:
        days_since_last = (now - commit_dates[-1]).days
    else:
        days_since_last = 999999

    # intervalos em dias
    intervals = []
    for i in range(1, len(commit_dates)):
        intervals.append((commit_dates[i] - commit_dates[i - 1]).days)

    median_days_between = 0 if not intervals else sorted(intervals)[len(intervals) // 2]

    return {
        "commits_total": commits_total,
        "authors_total": commits_per_author,
        "days_since_last_commit": days_since_last,
        "median_days_between_commits": median_days_between,
        "merge_commits": merge_commits,
    }
