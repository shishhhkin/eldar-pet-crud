from src.repository import Repo


class BaseService[RepoT: Repo]:
    def __init__(self, repo: RepoT) -> None:
        self.repo = repo
