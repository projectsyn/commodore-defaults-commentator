import copy
import reclass

from typing import Dict, Callable

from jinja2 import Environment, PackageLoader

from .inventory import AnnotatedInventory

def output(data):
    return reclass.output(data, "yaml", pretty_print=True, complex_params=True)


def prepare_component_data(ckey, cparams):
    params = copy.deepcopy(cparams)
    params.pop("_documentation", None)
    return {
        "title": ckey,
        "docu": cparams.get('_documentation', None),
        "params": params
    }

def render_template(inventory: AnnotatedInventory, filters: Dict[str, Callable]) -> str:
    components = []

    component_versions = {}
    all_component_versions = inventory.parameters(param="components", simplify=False)

    for app in inventory.applications:
        cn, alias = inventory.parse_app(app)
        if cn != alias:
            components.append(prepare_component_data(alias, inventory.parameters(param=alias)))
        components.append(prepare_component_data(cn, inventory.parameters(param=cn)))
        component_versions[cn] = all_component_versions[cn]

    return render_jinja(
        "component_description.adoc.jinja2",
        filters,
        components=components,
        component_versions=component_versions,
        distribution=inventory.distribution,
        cloud=inventory.cloud,
        region=inventory.region,
        repo=inventory.repo_url,
        repo_path=inventory.repo_path,
    )

def render_jinja(templatename, filters, **kwargs):
    env = Environment(loader=PackageLoader("commodore_defaults_commentator", "templates"))
    if filters:
        for fname, f in filters.items():
            print(f"Adding filter {fname}")
            env.filters[fname] = f

    tpl = env.get_template(templatename)

    return tpl.render(**kwargs)