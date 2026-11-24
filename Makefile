# The pipeline as a program (Session 5). Every target is a command you already know.
# Recipes must start with a TAB, not spaces.

# One version, in one place: pyproject.toml. Everything else reads it.
VERSION := $(shell python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
IMAGE ?= gozo-ferry
# Each image also carries the commit it was built from, so a tag is never reused for different code.
GIT_SHA := $(shell git rev-parse --short HEAD 2>/dev/null || echo nogit)
# On GitHub the workflow passes SOURCE, the repository address. The label links the image to the repository,
# and ghcr.io refuses a push from the workflow without it.
SOURCE ?=
LABELS := $(if $(SOURCE),--label org.opencontainers.image.source=$(SOURCE))
GATE_SPLIT ?= holdout

.PHONY: install lint test validate gate build publish up version ci train register champion ask profile kg-version kg-release

install:
	python3 -m pip install -r requirements.txt
	python3 -m pip install --no-deps -e ".[dev]"

lint:
	ruff check src tests

test:
	pytest -q

validate:
	gozo-validate

gate:
	gozo-gate --split $(GATE_SPLIT)

build:
	docker build --build-arg APP_VERSION=$(VERSION) -t $(IMAGE):$(VERSION) -t $(IMAGE):$(VERSION)-$(GIT_SHA) $(LABELS) .

publish:
	docker push $(IMAGE):$(VERSION)
	docker push $(IMAGE):$(VERSION)-$(GIT_SHA)

up:
	APP_VERSION=$(VERSION) docker compose up -d --build

# Session 6: train and track a run, then register it only if it passed the gate.
train:
	gozo-train

register: train
	gozo-registry register

# Point the champion alias at version V and restart the API, which loads it at start-up.
# Rolling back is the same command with the previous # Session 7: the operator's questions, answered from the log alone and through the ferry's knowledge.
# ROUTE=keyword or ROUTE=knowledge runs one route; SHOW=--show lists the log entries each route counted.
ROUTE ?= both
SHOW ?=
ask:
	gozo-ask questions --route $(ROUTE) $(SHOW)

profile:
	gozo-ask profile

# Session 7: the knowledge has a version of its own, kept in one place, kg/schema.yaml, and separate from the code's.
# A release of the knowledge is an annotated git tag on a commit whose tests pass, and a tag is never reused:
# git refuses to create one that exists. Push it with: git push origin kg-v$(KG_VERSION)
KG_VERSION := $(shell sed -n 's/^version: "\(.*\)"$$/\1/p' kg/schema.yaml)
kg-version:
	@echo $(KG_VERSION)

kg-release: test
	@git diff --quiet HEAD || \
		{ echo "Commit your changes before releasing the knowledge."; exit 1; }
	git tag -a kg-v$(KG_VERSION) -m "Gozo ferry knowledge $(KG_VERSION)"
	@echo "Push the tag with: git push origin kg-v$(KG_VERSION)"

version: make champion V=1
champion:
	gozo-registry alias champion $(V)
	docker compose restart api

version:
	@echo $(VERSION)

# The whole pipeline, in order. make stops at the first command that exits non-zero.
ci: lint test validate gate build
