# Harbor M0 - Phase Plan

Expand [HARBOR-PLAN.md](HARBOR-PLAN.md) milestone `M0 - Platform-ready project scaffold` into execution-ready steps. Run these steps in order. The phase exit gate is `make ci` green; shared workflow governance passes by local manifest/workflow checks; `docker compose` validates the stack without starting services.

## Phase Context

- Source milestone: [HARBOR-PLAN.md](HARBOR-PLAN.md) M0.
- Platform decision: [ADR-0001](docs/adr/0001-true-nas-platform-deployment.md).
- Backend decision: [ADR-0002](docs/adr/0002-python-fastapi-backend.md).
- Platform references: [../ahara/CI-WORKFLOW.md](../ahara/CI-WORKFLOW.md), [../ahara/TRUENAS-DEPLOY.md](../ahara/TRUENAS-DEPLOY.md), [../ahara/INTEGRATION.md](../ahara/INTEGRATION.md).
- Standards references: [project structure](../ahara-standards/standards/project-structure.md), [scripts](../ahara-standards/standards/scripts.md), [TypeScript](../ahara-standards/standards/typescript.md), [testing](../ahara-standards/standards/testing.md).

## Steps

1. Create runtime pins and platform manifest
   - File(s): `.python-version`, `.node-version`, `.env.example`, `platform.yml`, `.github/workflows/ci.yml`.
   - Reference behavior: M0 requires root platform files; Ahara CI reads `platform.yml`; Ahara standards require exact runtime pins and `.env.example` placeholders only.
   - Change: Pin Python to `3.12.13`, Node to `24.16.0`, declare `project: harbor`, `prefix: harbor`, `stack: [python, typescript]`, `truenas: true`, `images: [backend, frontend]`, and add the minimal shared workflow caller using `chris-arsenault/ahara/.github/workflows/ci.yml@main`. Keep `.env.example` to placeholders and safe defaults only.
   - Verify: Red before the files exist, green after:
     ```bash
     test "$(cat .python-version)" = "3.12.13"
     test "$(cat .node-version)" = "24.16.0"
     grep -q '^project: harbor$' platform.yml
     grep -q 'chris-arsenault/ahara/.github/workflows/ci.yml@main' .github/workflows/ci.yml
     grep -q 'OANDA_ENV=practice' .env.example
     ```

2. Create the backend Python package skeleton
   - File(s): `backend/pyproject.toml`, `backend/uv.lock`, `backend/src/harbor_bot/__init__.py`, `backend/src/harbor_bot/api.py`, `backend/src/harbor_bot/main.py`, `backend/tests/test_health.py`.
   - Reference behavior: [ADR-0002](docs/adr/0002-python-fastapi-backend.md) selects Python 3.12, FastAPI, asyncio, SQLAlchemy/Alembic, and `uv`; M0 asks for a health endpoint placeholder.
   - Change: Define the `harbor-bot` package with runtime dependencies for the planned backend boundary (`fastapi`, `uvicorn`, `httpx`, `pydantic-settings`, `sqlalchemy`, `asyncpg`, `alembic`, `structlog`, `pyyaml`) and dev dependencies (`pytest`, `pytest-asyncio`, `ruff`). Implement a minimal FastAPI app with `GET /health -> {"status": "ok"}` and a thin `main.py` entrypoint.
   - Verify: Red before the package/test exists, green after:
     ```bash
     cd backend
     uv sync --extra dev
     uv run --extra dev pytest
     uv run --extra dev ruff check src tests
     uv run --extra dev ruff format --check src tests
     ```

3. Create the frontend Vite shell
   - File(s): `frontend/package.json`, `frontend/pnpm-lock.yaml`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/App.test.tsx`, `frontend/src/test/setup.ts`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`.
   - Reference behavior: M0 requires Vite React TypeScript with a static health-checkable shell; Ahara TypeScript standards require pnpm, strict TypeScript, and Vitest.
   - Change: Create a Vite React app shell using only `.ts`/`.tsx` files, `packageManager: "pnpm@10.29.3"`, scripts for `lint`, `typecheck`, `test`, and `build`, and a tiny render/test that proves the app mounts.
   - Verify: Red before `package.json` and source files exist, green after:
     ```bash
     cd frontend
     pnpm install --frozen-lockfile
     pnpm exec tsc --noEmit
     pnpm exec vitest run
     pnpm run build
     ```

4. Add frontend styling and lint standards [depends on #3]
   - File(s): `frontend/eslint.config.js`, `frontend/.prettierrc`, `frontend/postcss.config.js`, `frontend/tailwind.config.ts`, `frontend/src/styles.css`, `frontend/package.json`, `frontend/pnpm-lock.yaml`.
   - Reference behavior: Ahara TypeScript standards require ESLint v9 flat config, Prettier settings, Tailwind for this product, and custom rules from `@ahara/standards/eslint-rules`.
   - Change: Add Tailwind wiring, import `src/styles.css` from `main.tsx`, install required ESLint plugins, configure the listed custom Ahara rules, and apply the standard Prettier config.
   - Verify: Red before lint config and styles exist, green after:
     ```bash
     cd frontend
     pnpm install --frozen-lockfile
     pnpm exec eslint .
     pnpm exec prettier --check .
     pnpm run build
     ```

5. Decide how Harbor handles Ahara's Python deploy hook [DECISION] [depends on #1, #2]
   - File(s): `scripts/build-lambda.sh`, `.github/workflows/ci.yml`, `platform.yml`, `HARBOR-PLAN.md` if the decision changes the deployment contract.
   - Reference behavior: The shared Ahara workflow runs `bash scripts/build-lambda.sh` on main whenever `stack` includes `python`; Harbor is a TrueNAS service, not a Python Lambda. The user-wide instruction requires surfacing unusual workflow repairs before writing them.
   - Change: Choose one path before implementation continues:
     - Recommended: add `scripts/build-lambda.sh` as a clearly named compatibility hook that validates backend packaging for TrueNAS and exits successfully without producing Lambda artifacts.
     - Alternative: call the shared workflow with `deploy: false` and add a custom deploy job for TrueNAS images and Komodo.
     - Alternative: omit `python` from `platform.yml` and keep Python checks in `make ci`, accepting weaker shared workflow autodetection.
   - Verify: Red before the chosen hook/workflow exists because a main-branch shared workflow deploy would fail at `bash scripts/build-lambda.sh`; green after the chosen path passes:
     ```bash
     test -x scripts/build-lambda.sh
     bash -n scripts/build-lambda.sh
     ```

6. Add TrueNAS compose, secrets, and component packaging [depends on #2, #3, #5]
   - File(s): `compose.yaml`, `secret-paths.yml`, `backend/Dockerfile`, `backend/.dockerignore`, `frontend/Dockerfile`, `frontend/nginx.conf`, `frontend/.dockerignore`.
   - Reference behavior: [ADR-0001](docs/adr/0001-true-nas-platform-deployment.md) requires separate backend/frontend images; Ahara TrueNAS deploy reads `secret-paths.yml`, builds images from each component directory, and injects `${IMAGE_TAG}` plus SSM-resolved environment variables.
   - Change: Define `backend` image `ghcr.io/chris-arsenault/harbor/backend:${IMAGE_TAG}` serving FastAPI on `8080`; define `frontend` image `ghcr.io/chris-arsenault/harbor/frontend:${IMAGE_TAG}` serving nginx on a host port reserved for Harbor; proxy `/api` and `/ws` to the backend service. Map DB credentials from `/ahara/truenas-db/harbor/app/{username,password,database}` and Harbor-specific OANDA/alert secret paths from `/ahara/harbor/...`. Use static compose values for `DB_HOST=192.168.66.3`, `DB_PORT=5432`, `OANDA_ENV=practice`, and `ALLOW_LIVE=false`.
   - Verify: Red before `compose.yaml` and image files exist, green after without starting services:
     ```bash
     docker compose --env-file .env.example config --quiet
     ```

7. Add the local deploy script [depends on #6]
   - File(s): `scripts/deploy.sh`, `scripts/build-lambda.sh` if #5 selected the compatibility hook.
   - Reference behavior: Ahara scripts standard requires a parameterless `scripts/deploy.sh` that does not source `.env`, uses platform defaults, and keeps local deploy separate from CI.
   - Change: Add an executable `scripts/deploy.sh` that runs the same local build/validation sequence as `make ci`, then reports that deployment happens through the Ahara shared CI/Komodo path.
   - Verify: Red before the script exists, green after:
     ```bash
     test -x scripts/deploy.sh
     bash -n scripts/deploy.sh
     ```

8. Expand the root Makefile into the full M0 gate [depends on #2, #3, #4, #6, #7]
   - File(s): `Makefile`.
   - Reference behavior: M0 exit requires `make ci`; Ahara standards require standard target names and CI parity with shared workflow lint/test steps.
   - Change: Replace the documentation-only gate with targets for backend install/lint/format/test, frontend install/lint/format/typecheck/test/build, compose config validation, shell syntax checks, and existing doc whitespace checks.
   - Verify: Red before the target references existing project files and green after:
     ```bash
     make ci
     ```

9. Refresh top-level docs for the executable scaffold [depends on #8]
    - File(s): `README.md`, `AGENTS.md`, `docs/development.md`, `CHANGELOG.md`.
    - Reference behavior: Repo-docs requires top-level files to stay index-style and current-state; M0 changes the repo from planning-only to an executable scaffold.
    - Change: Update quickstart and command tables to describe the actual M0 scaffold, `make ci`, and platform files without duplicating detailed architecture content.
    - Verify: Red before docs mention the old planning-only state, green after:
      ```bash
      ! grep -q 'Until M0 is executed' README.md
      grep -q 'make ci' README.md AGENTS.md docs/development.md
      git diff --check
      ```

## M0 Decision Register

| Step | Decision you own |
| ---- | ---- |
| #5 | Choose how Harbor handles the shared Ahara workflow's Python `scripts/build-lambda.sh` deploy hook for a non-Lambda TrueNAS backend. |

## Handoff

Execute only these M0 steps next. After M0 exits with `make ci` green, return to [HARBOR-PLAN.md](HARBOR-PLAN.md) and run `plan-phase` on M1 before touching `ahara-infra`.
