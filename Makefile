MAKEFLAGS += -j4

docker_cmd  ?= docker
docker_opts ?= --rm --tty --user "$$(id -u)"

vale_cmd           ?= $(docker_cmd) run $(docker_opts) --volume "$${PWD}"/docs/modules/ROOT/pages:/pages vshn/vale:2.6.1 --minAlertLevel=error --config=/pages/.vale.ini /pages
antora_preview_cmd ?= $(docker_cmd) run --rm --publish 35729:35729 --publish 2020:2020 --volume "${PWD}":/preview/antora vshn/antora-preview:2.3.7 --style=syn --antora=docs

.PHONY: all
all: docs

.PHONY: docs-serve
docs-serve:
	poetry run commodore-defaults-commentator render git@git.vshn.net:syn/commodore-defaults.git
	$(antora_preview_cmd)

.PHONY: preview
preview:
	$(antora_preview_cmd)

.PHONY: docs-vale
docs-vale:
	$(vale_cmd)
