from datetime import datetime, timedelta, timezone
from typing import Any, Dict

try:
    # PyDriller < 2.0
    from pydriller import RepositoryMining
except ImportError:  # pragma: no cover - exercised in envs with newer PyDriller
    # PyDriller >= 2.0 renamed RepositoryMining -> Repository with same traverse_commits API
    from pydriller import Repository as RepositoryMining


def analyze_activity(repo_path: str, since_days: int = 365) -> Dict[str, Any]:
    """
    Coleta métricas simples de atividade do repositório usando PyDriller.

    - commits_total: total de commits na janela
    - authors_total: número de autores distintos
    - days_since_last_commit: dias desde o último commit (0 se hoje)
    - median_days_between_commits: mediana dos intervalos entre commits
    - merge_commits: número de merges
    - top_authors: lista dos 5 autores com mais commits (ordenados)
    - recent_authors: lista dos 5 autores com commits mais recentes (com dias desde o último commit do autor)
    """
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=since_days)

    commit_dates = []
    author_counts = {}
    author_last_commit = {}
    merge_commits = 0

    for commit in RepositoryMining(path_to_repo=repo_path, since=since, to=now).traverse_commits():
        cdate = commit.committer_date
        if cdate.tzinfo is None:
            cdate = cdate.replace(tzinfo=timezone.utc)
        commit_dates.append(cdate)
        ident = (commit.author.email or commit.author.name or "").strip() or "unknown"
        author_counts[ident] = author_counts.get(ident, 0) + 1

        prev = author_last_commit.get(ident)
        if prev is None or cdate > prev:
            author_last_commit[ident] = cdate
        if getattr(commit, "merge", False) or (getattr(commit, "parents", None) and len(commit.parents) > 1):
            merge_commits += 1
        elif "merge" in (commit.msg or "").lower():
            merge_commits += 1

    commit_dates.sort()
    commits_total = len(commit_dates)
    authors_total = len(author_counts)

    if commit_dates:
        days_since_last = (now - commit_dates[-1]).days
    else:
        days_since_last = 999999

    intervals = []
    for i in range(1, len(commit_dates)):
        intervals.append((commit_dates[i] - commit_dates[i - 1]).days)
    median_days_between_commits = 0 if not intervals else sorted(intervals)[len(intervals) // 2]

    top_authors = [
        {"author": a, "commits": c}
        for a, c in sorted(author_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
    ]

    recent_sorted = sorted(author_last_commit.items(), key=lambda kv: kv[1], reverse=True)[:5]
    recent_authors = [
        {
            "author": a,
            "days_since_last_commit": (now - dt).days,
            "commits": author_counts.get(a, 0),
        }
        for a, dt in recent_sorted
    ]

    return {
        "commits_total": commits_total,
        "authors_total": authors_total,
        "days_since_last_commit": days_since_last,
        "median_days_between_commits": median_days_between_commits,
        "merge_commits": merge_commits,
        "top_authors": top_authors,
        "recent_authors": recent_authors,
    }
