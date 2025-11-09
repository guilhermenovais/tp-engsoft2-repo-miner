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
