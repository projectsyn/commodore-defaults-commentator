import reclass

from . import Config
from .inventory import AnnotatedInventory

def output(data):
    return reclass.output(data, "yaml", pretty_print=True, complex_params=True)

def render_documentation(cfg: Config):
    print(f"Rendering documentation for defaults repo at {cfg.repo}")
    inv = AnnotatedInventory.from_repo_url(cfg)
    r = inv.reclass("openshift4", "cloudscale", "lpg")
    print(output(r))
