SHELL := /bin/bash
PYTHON ?= python3
UV ?= $(shell if command -v uv >/dev/null 2>&1; then command -v uv; else printf '.tools/uv/bin/uv'; fi)
PNPM ?= env CI=true npm exec --yes pnpm@10.17.1 --
PY_RUN ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,$(UV) run python)
RUFF ?= $(if $(wildcard .venv/bin/ruff),.venv/bin/ruff,$(UV) run ruff)
MYPY ?= $(if $(wildcard .venv/bin/mypy),.venv/bin/mypy,$(UV) run mypy)
PYTEST ?= $(if $(wildcard .venv/bin/pytest),.venv/bin/pytest,$(UV) run pytest)
COMMERCE_AGENT ?= $(if $(wildcard .venv/bin/python),.venv/bin/python -m open_commerce.cli,$(UV) run commerce-agent)

.PHONY: setup ensure-uv bootstrap dev dev-local lint typecheck test test-integration test-e2e test-fault install-browser simulator-golden benchmark-search controller-eval controller-eval-smoke openapi check-openapi check verify demo-assets

setup:
	$(PYTHON) scripts/setup_self_hosted.py

ensure-uv:
	@if ! command -v uv >/dev/null 2>&1 && [ ! -x .tools/uv/bin/uv ]; then \
		$(PYTHON) -m pip install --target .tools/uv uv==0.8.15; \
	fi

bootstrap: ensure-uv
	$(PYTHON) scripts/sync_release_legal.py --check
	$(UV) sync --frozen --all-packages --group dev
	$(PNPM) install --frozen-lockfile
	$(MAKE) openapi

dev:
	docker compose up --build

dev-local:
	$(PY_RUN) -m open_commerce.local_runtime

lint: ensure-uv
	$(RUFF) check .
	$(RUFF) format --check .
	$(PNPM) lint

typecheck: ensure-uv
	$(MYPY) packages/backend/src scripts tests packages/backend/tests
	$(PNPM) typecheck

test: ensure-uv
	$(PYTEST) packages/backend/tests/unit tests/contract
	$(PNPM) test

test-integration: ensure-uv
	OPEN_COMMERCE_RUN_INTEGRATION=1 $(PYTEST) packages/backend/tests/integration tests/integration

test-e2e: ensure-uv
	$(PNPM) test:e2e

demo-assets:
	$(PNPM) --filter @open-commerce/web exec playwright test --config capture.config.ts

install-browser:
	$(PNPM) --filter @open-commerce/web exec playwright install chromium

test-fault: ensure-uv
	OPEN_COMMERCE_RUN_FAULTS=1 $(PYTEST) tests/fault

simulator-golden: ensure-uv
	$(COMMERCE_AGENT) simulator golden

benchmark-search: ensure-uv
	$(COMMERCE_AGENT) eval search --dataset examples/eval/search_queries_v2.jsonl --verify examples/eval/search-merchandising-v1/legacy-availability-regression.json

controller-eval: ensure-uv
	$(COMMERCE_AGENT) controller evaluate

controller-eval-smoke: ensure-uv
	$(COMMERCE_AGENT) controller evaluate --seeds 42 --days 3 --output .opencommerce/controller-smoke.json --verify examples/eval/results/controller-v2-smoke.json

openapi: ensure-uv
	$(PY_RUN) scripts/export_openapi.py
	$(PY_RUN) scripts/generate_ts_client.py

check-openapi: ensure-uv
	$(PY_RUN) scripts/export_openapi.py --check
	$(PY_RUN) scripts/generate_ts_client.py --check
	$(PY_RUN) scripts/sync_release_legal.py --check
	$(PY_RUN) scripts/check-release-paths.py

check: lint typecheck test simulator-golden benchmark-search controller-eval-smoke test-integration check-openapi

verify: check
