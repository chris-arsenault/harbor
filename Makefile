.PHONY: \
	backend-ci \
	backend-format \
	backend-format-check \
	backend-install \
	backend-lint \
	backend-test \
	backend-test-all \
	backend-test-e2e \
	backend-test-integration \
	ci \
	compose-config \
	deploy \
	format \
	format-check \
	frontend-build \
	frontend-ci \
	frontend-format \
	frontend-format-check \
	frontend-install \
	frontend-lint \
	frontend-test \
	frontend-typecheck \
	lint \
	lint-fix \
	shell-check \
	test \
	typecheck \
	verify-docs

ci: backend-ci frontend-ci compose-config shell-check verify-docs

backend-ci: backend-install backend-lint backend-format-check backend-test

backend-install:
	cd backend && uv sync --frozen --extra dev

backend-lint: backend-install
	cd backend && uv run --extra dev ruff check src tests

backend-format:
	cd backend && uv run --extra dev ruff format src tests

backend-format-check: backend-install
	cd backend && uv run --extra dev ruff format --check src tests

backend-test: backend-install
	cd backend && uv run --extra dev pytest tests --ignore=tests/integration --ignore=tests/e2e

backend-test-integration: backend-install
	cd backend && uv run --extra dev pytest tests/integration

backend-test-e2e: backend-install
	cd backend && uv run --extra dev pytest tests/e2e

backend-test-all: backend-install
	cd backend && uv run --extra dev pytest

frontend-ci: frontend-install frontend-lint frontend-format-check frontend-typecheck frontend-test frontend-build

frontend-install:
	cd frontend && pnpm install --frozen-lockfile

frontend-lint: frontend-install
	cd frontend && pnpm exec eslint .

frontend-format:
	cd frontend && pnpm exec prettier --write .

frontend-format-check: frontend-install
	cd frontend && pnpm exec prettier --check .

frontend-typecheck: frontend-install
	cd frontend && pnpm exec tsc --noEmit

frontend-test: frontend-install
	cd frontend && pnpm exec vitest run

frontend-build: frontend-install
	cd frontend && pnpm run build

compose-config:
	docker compose --env-file .env.example config --quiet

shell-check:
	bash -n scripts/build-lambda.sh scripts/deploy.sh scripts/smoke.sh

verify-docs:
	test -f README.md
	test -f AGENTS.md
	test -f CLAUDE.md
	test -f LICENSE
	test -f HARBOR-PLAN.md
	test -f docs/README.md
	test -f docs/architecture.md
	test -f docs/adr/README.md
	test -f docs/backlog.md
	git diff --check

lint: backend-lint frontend-lint

lint-fix:
	cd backend && uv run --extra dev ruff check --fix src tests
	cd frontend && pnpm exec eslint . --fix

format: backend-format frontend-format

format-check: backend-format-check frontend-format-check

typecheck: frontend-typecheck

test: backend-test frontend-test

deploy:
	scripts/deploy.sh
