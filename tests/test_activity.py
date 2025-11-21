from datetime import datetime, timedelta, timezone

from repo_miner import activity as activity_mod


class DummyCommit:
    def __init__(self, when, email="a@a", name="A", parents=None, msg=""):
        self.committer_date = when
        self.author = type("A", (), {"email": email, "name": name})
        self.parents = parents or []
        self.msg = msg
        self.merge = len(self.parents) > 1


class DummyRepo:
    def __init__(self, commits):
        self._commits = commits

    def traverse_commits(self):
        for c in self._commits:
            yield c


def test_activity_empty(monkeypatch, tmp_path):
    class Factory:
        def __init__(self, path_to_repo=None, since=None, to=None):
            pass

        def traverse_commits(self):
            return iter(())

    monkeypatch.setattr(activity_mod, "RepositoryMining", Factory)
    metrics = activity_mod.analyze_activity(str(tmp_path), since_days=30)
    assert metrics["commits_total"] == 0
    assert metrics["days_since_last_commit"] > 1000


def test_activity_with_merges(monkeypatch, tmp_path):
    base = datetime.now(timezone.utc) - timedelta(days=10)
    commits = [
        DummyCommit(base + timedelta(days=1)),
        DummyCommit(base + timedelta(days=3), parents=[1, 2], msg="Merge branch"),
        DummyCommit(base + timedelta(days=6)),
    ]

    def factory(path_to_repo=None, since=None, to=None):
        return DummyRepo(commits)

    monkeypatch.setattr(activity_mod, "RepositoryMining", factory)
    m = activity_mod.analyze_activity(str(tmp_path), since_days=30)
    assert m["commits_total"] == 3
    assert m["merge_commits"] >= 1
    assert m["median_days_between_commits"] in (2, 3)  # depends on rounding


def test_activity_top_authors_limit_and_order(monkeypatch, tmp_path):
    """Deve retornar no máximo 5 autores ordenados por commits desc."""
    base = datetime.now(timezone.utc) - timedelta(days=30)

    commits = []
    def add_commits(author_email: str, count: int, start_offset: int):
        for i in range(count):
            commits.append(
                DummyCommit(
                    base + timedelta(days=start_offset + i),
                    email=author_email,
                    name=author_email.split("@")[0],
                )
            )

    add_commits("a1@example.com", 1, 0)
    add_commits("a2@example.com", 2, 2)
    add_commits("a3@example.com", 3, 5)
    add_commits("a4@example.com", 4, 9)
    add_commits("a5@example.com", 5, 14)
    add_commits("a6@example.com", 6, 20)

    def factory(path_to_repo=None, since=None, to=None):
        return DummyRepo(commits)

    monkeypatch.setattr(activity_mod, "RepositoryMining", factory)
    metrics = activity_mod.analyze_activity(str(tmp_path), since_days=60)

    assert "top_authors" in metrics
    top = metrics["top_authors"]
    assert len(top) == 5  # limite
    commits_counts = [item["commits"] for item in top]
    assert commits_counts == sorted(commits_counts, reverse=True)
    
    # autores esperados (os 5 com mais commits)
    expected_authors = {"a6@example.com", "a5@example.com", "a4@example.com", "a3@example.com", "a2@example.com"}
    returned_authors = {item["author"] for item in top}
    assert returned_authors == expected_authors


def test_activity_recent_authors(monkeypatch, tmp_path):
    """Deve retornar autores mais recentes com dias_since_last_commit em ordem crescente."""
    now = datetime.now(timezone.utc)
    base = now - timedelta(days=15)

    commits = [
        # a1: último commit há ~14 dias
        DummyCommit(base + timedelta(days=1), email="a1@example.com", name="a1"),
        # a2: commits incluindo o mais recente (dia 14) -> mais recente
        DummyCommit(base + timedelta(days=2), email="a2@example.com", name="a2"),
        DummyCommit(base + timedelta(days=14), email="a2@example.com", name="a2"),
        # a3: último commit dia 13
        DummyCommit(base + timedelta(days=5), email="a3@example.com", name="a3"),
        DummyCommit(base + timedelta(days=13), email="a3@example.com", name="a3"),
        # a4: último commit dia 10
        DummyCommit(base + timedelta(days=10), email="a4@example.com", name="a4"),
        # a5: último commit dia 8
        DummyCommit(base + timedelta(days=8), email="a5@example.com", name="a5"),
        # a6: último commit dia 6 (entra ou não dependendo de corte top 5)
        DummyCommit(base + timedelta(days=6), email="a6@example.com", name="a6"),
    ]

    def factory(path_to_repo=None, since=None, to=None):
        return DummyRepo(commits)

    monkeypatch.setattr(activity_mod, "RepositoryMining", factory)
    metrics = activity_mod.analyze_activity(str(tmp_path), since_days=30)
    assert "recent_authors" in metrics
    recent = metrics["recent_authors"]
    assert 1 <= len(recent) <= 5

    # Ordem esperada: a2 (mais recente), a3, a4? a5? dependendo do intervalo real de dias
    days_list = [r["days_since_last_commit"] for r in recent]
    assert days_list == sorted(days_list)

    for item in recent:
        assert "author" in item and "days_since_last_commit" in item and "commits" in item
