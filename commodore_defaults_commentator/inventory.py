import os
import shutil

import yaml

from pathlib import Path
from typing import Dict, Optional

import reclass
import reclass.core

from commodore.cluster import Cluster, render_params
from commodore.config import Config as CommodoreConfig
from commodore.git import clone_repository
from commodore.inventory import Inventory

from git import Repo

from . import Config

class AnnotatedInventory:
    def __init__(self, work_dir: Path):
        self._inventory = Inventory(work_dir=work_dir)
        pass

    @property
    def directory(self) -> Path:
        return self._inventory.inventory_dir

    @property
    def classes_dir(self) -> Path:
        return self._inventory.classes_dir

    @property
    def targets_dir(self) ->Path:
        return self._inventory.targets_dir

    @property
    def repo(self) -> Repo:
        return self._repo

    @repo.setter
    def repo(self, repo):
        self._repo = repo

    def _reclass_config(self) -> Dict:
        return {
            "storage_type": "yaml_fs",
            "inventory_base_uri": str(self.directory.absolute()),
            "nodes_uri": str(self.targets_dir.absolute()),
            "classes_uri": str(self.classes_dir.absolute()),
            "compose_node_name": False,
            "allow_none_override": True,
            "ignore_class_notfound": True,
        }

    def reclass(self, distribution: str, cloud: str, region: Optional[str]=None):
        c = {
            "id": "c-bar",
            "tenant": "t-foo",
            "displayName": "Foo Inc. Bar cluster",
            "facts": {
                "distribution": distribution,
                "cloud": cloud,
                "lieutenant-instance": "lieutenant-prod",
            },
            "gitRepo": {
                "url": "not-a-real-repo",
            }
        }
        if region:
            c["facts"]["region"] = region

        cluster = Cluster(
            cluster_response=c,
            tenant_response={
                "id": "t-foo",
                "displayName": "Foo Inc.",
                "gitRepo": {
                    "url": "not-a-real-repo",
                }
            }
        )
        params = render_params(self._inventory, cluster)
        params["parameters"]["openshift"] = {
            "infraID": "infra-id",
            "clusterID": "clutster-id",
        }
        with open(self.classes_dir / "target.yml", "w") as f:
            yaml.dump(params, f)
        with open(self.targets_dir / "global.yml", "w") as f:
            yaml.dump({
               "classes": [
                "target",
                "global.commodore"
               ]
            }, f)
        rc = self._reclass_config()
        storage = reclass.get_storage(
            rc["storage_type"],
            rc["nodes_uri"],
            rc["classes_uri"],
            rc["compose_node_name"]
        )
        class_mappings = rc.get("class_mappings")
        _reclass = reclass.core.Core(storage, class_mappings, reclass.settings.Settings(rc))
        return _reclass.inventory(keep_uris=True)

    @classmethod
    def _make_directories(cls, cfg: Config):
        os.makedirs(cfg.workdir / "inventory" / "targets", exist_ok=True)
        os.makedirs(cfg.workdir / "inventory" / "classes", exist_ok=True)

    @classmethod
    def from_repo_url(cls, cfg: Config):
        cls._make_directories(cfg)
        i = AnnotatedInventory(work_dir=cfg.workdir)
        cc = CommodoreConfig(work_dir=cfg.workdir)
        print(cfg.repo)
        i.repo = clone_repository(cfg.repo, i.classes_dir / "global", cc)
        return i