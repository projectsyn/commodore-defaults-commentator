import os

import yaml

from reclass.utils.parameterdict import ParameterDict
from reclass.utils.parameterlist import ParameterList
from reclass.values.value import Value

from commodore.component import component_parameters_key

from . import Config
from .inventory import AnnotatedInventoryFactory
from .render_template import render_template, render_jinja


def _represent_value(dumper, data):
    return dumper.represent_data(data.contents)

def _represent_str(dumper, data):
    """
    Custom string rendering when dumping data as YAML.

    Hooking this method into PyYAML with

        yaml.add_representer(str, _represent_str)

    will configure the YAML dumper to render strings which contain newline
    characters as block scalars with the last newline stripped.
    """
    style = None
    if "\n" in data:
        style = "|"
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


class YamlAnnotator:
    def __init__(self):
        self._annotation_ids = {}
        self._next_annotation_id = 1

    def _dump_yaml(self, data):
        d = yaml.SafeDumper
        d.add_representer(Value, _represent_value)
        d.add_representer(str, _represent_str)
        y = yaml.dump(data, default_flow_style=False, Dumper=d)
        return list(
            filter(lambda l: l != "..." and l != "", y.split("\n"))
        )

    def annotate_key(self, key, data, scalar=""):
        annotationid = None
        if isinstance(data, ParameterDict) or \
                isinstance(data, ParameterList) or \
                isinstance(data, Value):
            annotationid = self._annotation_ids.setdefault(data.uri, self._next_annotation_id)
            if annotationid == self._next_annotation_id:
                self._next_annotation_id += 1
        annot = ""
        if annotationid is not None:
            annot = f" <{annotationid}>"
        if scalar != "":
            scalar = f" {scalar}"
        return f"{key}:{scalar}{annot}"

    def _render_complex_section(self, key, data):
        output_lines = [self.annotate_key(key, data)]
        if isinstance(data, ParameterDict) or isinstance(data, dict):
            for key, value in data.items():
                output_lines.extend(map(
                    lambda l: "  " + l,
                    self._render_complex_section(key, value)
                ))
        elif isinstance(data, ParameterList) or isinstance(data, list):
            # TODO: figure out if we can/want to have locations for individual list items
            output_lines.extend(map(lambda l: "  " + l, self._dump_yaml(list(data))))
        else:
            v = data
            if isinstance(v, Value):
                v = data.contents
            v = self._dump_yaml(v)
            output_lines = [self.annotate_key(key, data, scalar=v[0])]
            if len(v) > 1:
                output_lines.extend(v[1:])
        return output_lines

    def asciidoc_yaml_block(self, pkey, cparams, repo_path):
        if len(cparams) == 0:
            return "\n".join([
                "[source,yaml]",
                "----",
                f"{pkey}: {{}}",
                "----"
            ])

        source_lines = [
            "[source,yaml]",
            "----",
        ]
        source_lines.extend(self._render_complex_section(pkey, cparams))
        source_lines.append('----')
        for loc, annotationid in sorted(self._annotation_ids.items(), key=lambda it: it[1]):
            loc = strip_prefix(loc, repo_path)
            source_lines.append(f"<{annotationid}> `{loc}`")
        return '\n'.join(source_lines)


def asciidoc_yaml(params, pkey, repo_path):
    y = YamlAnnotator()
    return y.asciidoc_yaml_block(component_parameters_key(pkey), params, repo_path)

def strip_prefix(value, repo_path):
    if not isinstance(value, str):
        return value
    prefix = f"yaml_fs://{repo_path}/"
    if value.startswith(prefix):
        return value[len(prefix):]
    return value

def render_documentation(cfg: Config):
    print(f"Rendering documentation for defaults repo at {cfg.repo}")
    invfactory = AnnotatedInventoryFactory.from_repo_url(cfg)

    docsbase = cfg.workdir / "docs" / "modules" / "ROOT"

    filters = {
        "asciidoc_yaml": asciidoc_yaml,
        "strip_prefix": strip_prefix,
    }

    with open(docsbase / "pages" / "index.adoc", "w") as f:
        f.write(render_jinja("index.adoc.jinja2", None, repo_url=cfg.repo))

    navitems = {}

    cloud_regions = {
        "cloudscale": [ "lpg", "rma" ],
        "exoscale": ["ch-gva-2", "ch-dk-2"],
    }

    for distribution in [ "openshift4", "openshift3", "rancher", "k3d" ]:
        navitems[distribution] = {}
        for cloud in ["cloudscale", "exoscale"]:
            for region in cloud_regions[cloud]:
                inv = invfactory.reclass(distribution, cloud, region)

                navitems[distribution][f"{cloud}/{region}"] =  f"{distribution}/{cloud}_{region}.adoc"

                outf = docsbase / "pages" / distribution / f"{cloud}_{region}.adoc"
                os.makedirs(outf.parent, exist_ok=True)

                with open(outf, 'w') as f:
                    f.write(render_template(inv, filters))

    navf = docsbase / "nav.adoc"
    with open(navf, "w") as f:
        f.write(render_jinja("nav.adoc.jinja2", None, navitems=navitems))
