import reclass

from . import Config
from .inventory import AnnotatedInventory
from .render_template import render_template


def render_documentation(cfg: Config):
    print(f"Rendering documentation for defaults repo at {cfg.repo}")
    inv = AnnotatedInventory.from_repo_url(cfg)
    r = inv.reclass("openshift4", "cloudscale", "lpg")
    with open('./component_versions.adoc', 'w') as f:
        f.write(render_template(r))
