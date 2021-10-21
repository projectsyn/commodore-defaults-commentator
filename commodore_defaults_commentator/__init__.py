__version__ = '0.1.0'
__git_version__ = ''

from pathlib import Path

class Config:
    def __init__(self, workdir: Path):
        self._workdir: Path = workdir
        pass

    @property
    def repo(self) -> str:
        return self._repo

    @repo.setter
    def repo(self, repo: str):
        self._repo = repo

    @property
    def workdir(self) -> Path:
        return  self._workdir