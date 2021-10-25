import os

import yaml

from enum import Enum
from pathlib import Path
from typing import Iterable

from reclass.utils.parameterdict import ParameterDict
from reclass.utils.parameterlist import ParameterList
from reclass.values.value import Value
from reclass.values.scaitem import ScaItem

from commodore.component import component_parameters_key

from . import Config
from .inventory import AnnotatedInventoryFactory, value_is_complex
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


def _represent_parameter_list(dumper, data):
    annotid = dumper.annotation_ids.setdefault(data.uri, dumper.next_annotation_id)
    print(f"would annotate with {annotid}")
    return dumper.represent_list(list(data))


def _represent_parameter_dict(dumper, data):
    annotid = dumper.annotation_ids.setdefault(data.uri, dumper.next_annotation_id)
    print(f"would annotate with {annotid}")
    return dumper.represent_dict(dict(data))

def _represent_reference(dumper, data):
    return dumper.represent_data(f"${{{data.contents}}}")


class YamlAnnotator:
    def __init__(self):
        self._annotation_ids = {}
        self._next_annotation_id = 1

    def _dump_yaml(self, data):
        d = yaml.SafeDumper
        d.annotation_ids = self._annotation_ids
        d.next_annotation_id = self._next_annotation_id
        d.add_representer(Value, _represent_value)
        d.add_representer(ParameterList, _represent_parameter_list)
        d.add_representer(ParameterDict, _represent_parameter_dict)
        d.add_representer(ScaItem, _represent_reference)
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
        if key is None:
            return f"{scalar}{annot}"
        return f"{key}:{scalar}{annot}"

    def _render_complex_section(self, key, data):
        output_lines = [self.annotate_key(key, data)]
        if isinstance(data, ParameterDict) or isinstance(data, dict):
            for k, value in data.items():
                output_lines.extend(map(
                    lambda l: "  " + l,
                    self._render_complex_section(k, value)
                ))
            if key is None:
                first = output_lines.pop(0)
                newout = []
                extra = []
                for l in output_lines:
                    if l.endswith('>'):
                        newout.append(l)
                    elif l.endswith(':') or l[3] != " ":
                        newout.append(f"{l}{first}")
                    else:
                        newout.append(l)
                output_lines = newout
        elif isinstance(data, ParameterList) or isinstance(data, list):
            for item in data:
                listit = self._render_complex_section(None, item)
                output_lines.append(f"  - {listit[0].lstrip()}")
                output_lines.extend(map(lambda l: "  " + l, listit[1:]))
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
            source_lines.append(f"<{annotationid}> {loc}")
        return '\n'.join(source_lines)


def asciidoc_yaml(params, pkey, repo_path):
    y = YamlAnnotator()
    return y.asciidoc_yaml_block(component_parameters_key(pkey), params, repo_path)


def strip_prefix(value, repo_path):
    if not isinstance(value, str):
        return value
    prefix = f"yaml_fs://{repo_path}/"
    if value.startswith(prefix):
        return f"`{value[len(prefix):]}`"
    elif value.endswith("target.yml"):
        return "cluster fact"
    return value

class DefaultsFact(Enum):
    DISTRIBUTION = "distribution"
    CLOUD = "cloud"
    REGION = "region"

def find_values(fact: DefaultsFact, repo_path: Path, cloud: str = None) -> Iterable[str]:
    values = []
    value_path = repo_path / fact.value
    if fact == DefaultsFact.REGION:
        if not cloud:
            raise ValueError(f"cloud must not be None if fact is {fact}")
        value_path = repo_path / "cloud" / cloud
    if value_path.is_dir():
        for f in value_path.iterdir():
            if f.is_file() and f.suffix == ".yml":
                values.append(f.stem)
    return values


def render_documentation(cfg: Config):
    print(f"Rendering documentation for defaults repo at {cfg.repo}")
    invfactory = AnnotatedInventoryFactory.from_repo_url(cfg)

    docsbase = cfg.workdir / "docs" / "modules" / "ROOT"
    os.makedirs(docsbase / "pages", exist_ok=True)

    filters = {
        "asciidoc_yaml": asciidoc_yaml,
        "strip_prefix": strip_prefix,
    }

    with open(docsbase / "pages" / "index.adoc", "w") as f:
        f.write(render_jinja("index.adoc.jinja2", None, repo_url=cfg.repo))

    navitems = {}


    defaults_path = Path(invfactory.repo.working_tree_dir)
    distributions = find_values(DefaultsFact.DISTRIBUTION, defaults_path)
    clouds = find_values(DefaultsFact.CLOUD, defaults_path)
    cloud_regions = {}
    for cloud in clouds:
        cloud_regions[cloud] = find_values(DefaultsFact.REGION, defaults_path, cloud=cloud)

    for distribution in distributions:
        navitems[distribution] = {}
        for cloud in clouds:
            for region in cloud_regions[cloud]:
                if region == "params":
                    continue
                print(f"{distribution=}, {cloud=}, {region=}")
                inv = invfactory.reclass(distribution, cloud, region)

                navitems[distribution][f"{cloud}/{region}"] =  f"{distribution}/{cloud}_{region}.adoc"

                outf = docsbase / "pages" / distribution / f"{cloud}_{region}.adoc"
                os.makedirs(outf.parent, exist_ok=True)

                with open(outf, 'w') as f:
                    f.write(render_template(inv, filters))

    navf = docsbase / "nav.adoc"
    with open(navf, "w") as f:
        f.write(render_jinja("nav.adoc.jinja2", None, navitems=navitems))
