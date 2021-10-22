import copy
import reclass

from jinja2 import Environment, FileSystemLoader


def output(data):
    return reclass.output(data, "yaml", pretty_print=True, complex_params=True)


def render_template(dict_data: dict) -> str:
    components = []

    if not isinstance(dict_data, dict):
        raise TypeError()

    for k, v in dict_data["nodes"]["global"]["parameters"].items():
        if k == "_reclass_":
            continue

        params = copy.deepcopy(v)

        params.pop("_documentation", None)

        components.append({
            "title": k,
            "docu": v.get('_documentation', None),
            "params": output(params)
        })

    env = Environment(loader=FileSystemLoader("templates"))
    tpl = env.get_template("component_description.adoc.jinja2")

    return tpl.render(components=components)
