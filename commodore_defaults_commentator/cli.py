import shutil

import click
import shutil

from pathlib import Path

from . import __version__, __git_version__, Config
from .render import render_documentation


pass_config = click.make_pass_decorator(Config)

prog_name="commodore-defaults-commentator"

def _version():
    if f"v{__version__}" != __git_version__:
        return f"{__version__} (Git version: {__git_version__})"
    return __version__

@click.group()
@click.version_option(_version(), prog_name=prog_name)
@click.option(
    "-d",
    "--working-dir",
    default="./",
    show_default=True,
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    envvar="WORKING_DIR",
    help=(
            "The directory in which the Commodore defaults commentator will fetch the inventory " +
            "store intermediate outputs, and render the documentation"
    ),
)
@click.pass_context
def commentator(ctx, working_dir):
    ctx.obj = Config(workdir=working_dir)

@commentator.command(name="render", short_help="Render commodore-defaults documentation")
@click.argument("defaults-repo")
@pass_config
def render(config: Config, defaults_repo: str):
    config.repo = defaults_repo
    shutil.rmtree("inventory")
    render_documentation(config)

def main():
    commentator.main(prog_name=prog_name, auto_envvar_prefix="COMMENTATOR")
