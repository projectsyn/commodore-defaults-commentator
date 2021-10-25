import os

import yaml

from pathlib import Path
from typing import Dict, Optional, Tuple, Any

import reclass
import reclass.core

from commodore.cluster import Cluster, render_params
from commodore.component import component_parameters_key
from commodore.config import Config as CommodoreConfig
from commodore.git import clone_repository
from commodore.inventory import Inventory

from reclass.utils.parameterdict import ParameterDict
from reclass.utils.parameterlist import ParameterList
from reclass.values.value import Value

from git import Repo

from . import Config

def value_is_complex(v: Any) -> bool:
    return isinstance(v, Value) or isinstance(v, ParameterDict) or isinstance(v, ParameterList)


class AnnotatedInventory:
    def __init__(self, inv, node, distribution, cloud, region, repo):
        self._inventory = inv
        self._node = node
        self._distribution = distribution
        self._cloud = cloud
        self._region = region
        self._repo: Repo = repo

    @property
    def distribution(self):
        return  self._distribution

    @property
    def cloud(self):
        return  self._cloud

    @property
    def region(self):
        return  self._region

    @property
    def repo_url(self):
        return next(self._repo.remote().urls)

    @property
    def repo_path(self):
        return  self._repo.working_dir

    def parse_app(self, app: str) -> Tuple[str, str]:
        try:
            cn, alias = app.split(" as ")
        except ValueError:
            cn = app
            alias = app

        return cn, alias

    def parameters(self, param: Optional[str] = None, simplify=True):
        params = self._inventory["nodes"][self._node]["parameters"]
        if param is not None:
            params =  params.get(component_parameters_key(param), {})

        if len(params) == 0:
            return params

        if simplify:
            return self._inner_simplify_param_uris(params)
        else:
            return params

    def _unwrap(self, val):
        if isinstance(val, Value):
            return val.contents
        elif isinstance(val, ParameterList):
            return list(val)
        elif isinstance(val, ParameterDict):
            return dict(val)
        else:
            raise Exception(f"Cannot unwrap type '{type(val)}'")

    def _inner_simplify_value(self, container, key, value, cururi):
        newval = self._inner_simplify_param_uris(value)
        if value_is_complex(value) and type(newval) == type(value):
            if newval.uri == cururi:
                newval = self._unwrap(newval)
        container[key] = newval

    def _inner_simplify_param_uris(self, params):
        if isinstance(params, ParameterDict):
            new = ParameterDict(uri=params.uri)
            for key, value in params.items():
                self._inner_simplify_value(new, key, value, params.uri)
            return new
        elif isinstance(params, ParameterList):
            new = ParameterList(uri=params.uri)
            for item in params:
                new.append(None)
                self._inner_simplify_value(new, -1, item, params.uri)
            return new
        else:
            return params


    @property
    def applications(self):
        return self._inventory["nodes"][self._node]["applications"]


class AnnotatedInventoryFactory:
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

    def reclass(self, distribution: str, cloud: str, region: Optional[str]=None) -> AnnotatedInventory:
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
        # don't support legacy component_versions key
        del(params["parameters"]["components"])
        del(params["parameters"]["component_versions"])
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
        return AnnotatedInventory(_reclass.inventory(keep_uris=True), "global", distribution, cloud, region, self._repo)


    @classmethod
    def _make_directories(cls, cfg: Config):
        os.makedirs(cfg.workdir / "inventory" / "targets", exist_ok=True)
        os.makedirs(cfg.workdir / "inventory" / "classes", exist_ok=True)

    @classmethod
    def from_repo_url(cls, cfg: Config):
        cls._make_directories(cfg)
        i = AnnotatedInventoryFactory(work_dir=cfg.workdir)
        cc = CommodoreConfig(work_dir=cfg.workdir)
        i.repo = clone_repository(cfg.repo, i.classes_dir / "global", cc)
        return i

