# Harbor M1 - Phase Plan

Expand [HARBOR-PLAN.md](HARBOR-PLAN.md) milestone `M1 - Ahara infra registration` into execution-ready steps. Run these steps in order. The phase exit gate is Harbor `make ci` green; `ahara-infra` Terraform formatting/checks green for touched files; planned DB and deployer changes visible in Terraform plan; Harbor's LAN endpoint verified by compose with no reverse-proxy route.

## Phase Context

- Source milestone: [HARBOR-PLAN.md](HARBOR-PLAN.md) M1.
- Platform decision: [ADR-0001](docs/adr/0001-true-nas-platform-deployment.md).
- Harbor platform files from M0: [platform.yml](platform.yml), [compose.yaml](compose.yaml), [secret-paths.yml](secret-paths.yml).
- Platform references: [../ahara/INTEGRATION.md](../ahara/INTEGRATION.md), [../ahara/TRUENAS-DEPLOY.md](../ahara/TRUENAS-DEPLOY.md), [../ahara/CI-WORKFLOW.md](../ahara/CI-WORKFLOW.md).
- LAN deployment reference: [../sulion/compose.yaml](../sulion/compose.yaml) and [../sulion/docs/deploy.md](../sulion/docs/deploy.md). Sulion publishes `192.168.66.3:<port>` directly on the LAN and has no `reverse_proxy_routes` entry.
- Ahara infra references:
  - `/home/dev/repos/ahara-infra/infrastructure/terraform/control/project-airwave.tf`
  - `/home/dev/repos/ahara-infra/infrastructure/terraform/control/project-sulion.tf`
  - `/home/dev/repos/ahara-infra/infrastructure/terraform/control/modules/managed-project/variables.tf`
  - `/home/dev/repos/ahara-infra/infrastructure/terraform/services/db-migrate-truenas.tf`
  - `/home/dev/repos/ahara-infra/infrastructure/terraform/network/locals.tf` only as a negative check: Harbor must not be added to `local.reverse_proxy_routes`.

## Working Tree Constraint

`/home/dev/repos/ahara-infra` already contains unrelated dirty changes. Preserve them. Do not revert, format, or rewrite unrelated files beyond the exact M1 targets unless a step explicitly names them.

## Steps

1. Confirm M0 Harbor baseline before cross-repo edits
   - File(s): `Makefile`, `platform.yml`, `compose.yaml`, `secret-paths.yml`.
   - Reference behavior: M1 depends on M0; M1 should register the exact Harbor platform contract created in M0.
   - Change: No file changes. Confirm Harbor declares project `harbor`, TrueNAS images, frontend LAN binding `192.168.66.3:30091:80`, and SSM paths under `/ahara/truenas-db/harbor/app/*` and `/ahara/harbor/*`.
   - Verify: Red if M0 drifted, green when Harbor matches the M1 contract:
     ```bash
     make ci
     grep -q '^project: harbor$' platform.yml
     grep -q '192.168.66.3:30091:80' compose.yaml
     grep -q '/ahara/truenas-db/harbor/app/username' secret-paths.yml
     grep -q '/ahara/harbor/oanda-api-token' secret-paths.yml
     ```

2. Add Harbor managed-project registration
   - File(s): `/home/dev/repos/ahara-infra/infrastructure/terraform/control/project-harbor.tf`.
   - Reference behavior: M1 requires `project-harbor.tf` with allowed repo `harbor`, state key `projects/harbor`, and `terraform-state` plus `komodo-deploy` policy modules. `project-airwave.tf` is the closest existing TrueNAS-only deployer pattern. `ssm_additional_parameter_paths` exists for project-specific SSM path write permissions.
   - Change: Create a new managed-project module named `project_harbor` with:
     - `allowed_repos = ["harbor"]`
     - `allowed_branches = ["main"]`
     - `allow_pull_request = true`
     - `prefix = "harbor"`
     - `state_key_prefix = "projects/harbor"`
     - `policy_modules = ["terraform-state", "komodo-deploy", "ssm-write"]`
     - `ssm_additional_parameter_paths = ["ahara/harbor/*"]`
   - Verify: Red before the file exists, green after:
     ```bash
     test -f /home/dev/repos/ahara-infra/infrastructure/terraform/control/project-harbor.tf
     grep -q 'allowed_repos      = \\["harbor"\\]' /home/dev/repos/ahara-infra/infrastructure/terraform/control/project-harbor.tf
     grep -q 'state_key_prefix = "projects/harbor"' /home/dev/repos/ahara-infra/infrastructure/terraform/control/project-harbor.tf
     grep -q '"komodo-deploy"' /home/dev/repos/ahara-infra/infrastructure/terraform/control/project-harbor.tf
     grep -q '"ssm-write"' /home/dev/repos/ahara-infra/infrastructure/terraform/control/project-harbor.tf
     grep -q '"ahara/harbor/\\*"' /home/dev/repos/ahara-infra/infrastructure/terraform/control/project-harbor.tf
     terraform -chdir=/home/dev/repos/ahara-infra/infrastructure/terraform/control fmt -check project-harbor.tf
     ```

3. Register Harbor TrueNAS PostgreSQL database
   - File(s): `/home/dev/repos/ahara-infra/infrastructure/terraform/services/db-migrate-truenas.tf`.
   - Reference behavior: Ahara TrueNAS DB registry maps stack names to database IDs and `db_name` values. Harbor `secret-paths.yml` expects database ID `app` at `/ahara/truenas-db/harbor/app/{username,password,database}`.
   - Change: Add a `harbor` entry to `var.truenas_db_stacks.default` with `databases.app.db_name = "harbor"`. Keep existing `sonarqube` and `sulion` entries unchanged.
   - Verify: Red before the registry contains Harbor, green after:
     ```bash
     grep -q '^    harbor = {' /home/dev/repos/ahara-infra/infrastructure/terraform/services/db-migrate-truenas.tf
     grep -q 'db_name = "harbor"' /home/dev/repos/ahara-infra/infrastructure/terraform/services/db-migrate-truenas.tf
     terraform -chdir=/home/dev/repos/ahara-infra/infrastructure/terraform/services fmt -check db-migrate-truenas.tf
     ```

4. Verify Harbor remains LAN-only [depends on #1]
   - File(s): [compose.yaml](compose.yaml), `/home/dev/repos/ahara-infra/infrastructure/terraform/network/locals.tf`.
   - Reference behavior: Sulion publishes its frontend as `192.168.66.3:<port>:80` in compose and has no `reverse_proxy_routes` entry. Harbor follows that LAN deployment pattern: frontend port `30091` is bound directly to the TrueNAS LAN IP, and `ahara-infra` network routes must not include `harbor.services.ahara.io` or port `30091`.
   - Change: If a Harbor reverse-proxy route is present, remove only that route. If the compose file is not bound to `192.168.66.3:30091:80`, update only the frontend port binding. Preserve existing non-Harbor route entries and comments.
   - Verify: Red when Harbor is not LAN-only, green when compose owns `30091` and `ahara-infra` has no Harbor reverse-proxy route:
     ```bash
     grep -q '192.168.66.3:30091:80' /home/dev/repos/harbor/compose.yaml
     ! rg -n '"harbor.services.ahara.io"|port\s*=\s*30091' /home/dev/repos/ahara-infra/infrastructure/terraform/network/locals.tf
     rg -n 'port\s*=\s*30091|30091' /home/dev/repos/ahara-infra/infrastructure/terraform/network /home/dev/repos/harbor/compose.yaml
     terraform -chdir=/home/dev/repos/ahara-infra/infrastructure/terraform/network fmt -check locals.tf
     ```
     Confirm the `rg` output contains only Harbor's compose file.

5. Verify Harbor secret paths are covered by deployer permissions [depends on #2]
   - File(s): `/home/dev/repos/ahara-infra/infrastructure/terraform/control/project-harbor.tf`, [secret-paths.yml](secret-paths.yml).
   - Reference behavior: Harbor `secret-paths.yml` uses `/ahara/harbor/*` for OANDA and alert secrets. The deployer role needs write access for project-specific SSM paths through `ssm-write`; TrueNAS DB SSM paths are written by the platform DB Lambda, not by Harbor.
   - Change: Adjust only `project-harbor.tf` if step #2 missed an SSM path needed by `secret-paths.yml`. Do not add broad `/ahara/*` access.
   - Verify: Red if any Harbor-specific path is not under `ahara/harbor/*`, green when permissions and paths match:
     ```bash
     python3 - <<'PY'
     from pathlib import Path
     import yaml
     paths = yaml.safe_load(Path("secret-paths.yml").read_text())
     harbor_paths = [p for p in paths.values() if p.startswith("/ahara/harbor/")]
     assert harbor_paths, "expected Harbor-specific secret paths"
     assert all(p.startswith("/ahara/harbor/") for p in harbor_paths)
     project = Path("/home/dev/repos/ahara-infra/infrastructure/terraform/control/project-harbor.tf").read_text()
     assert '"ssm-write"' in project
     assert '"ahara/harbor/*"' in project
     PY
     ```

6. Run scoped formatting and preserve unrelated ahara-infra changes
   - File(s): `/home/dev/repos/ahara-infra/infrastructure/terraform/control/project-harbor.tf`, `/home/dev/repos/ahara-infra/infrastructure/terraform/services/db-migrate-truenas.tf`, `/home/dev/repos/ahara-infra/infrastructure/terraform/network/locals.tf`.
   - Reference behavior: M1 exit requires ahara-infra Terraform formatting/checks green for touched files, while preserving unrelated dirty changes. `network/locals.tf` is checked only to prove Harbor is absent from reverse-proxy routes.
   - Change: Run Terraform formatting on only the touched files if required. Do not run repo-wide formatting if it would modify unrelated dirty files.
   - Verify: Green when touched files are formatted and unrelated dirty files are still not edited by M1:
     ```bash
     terraform -chdir=/home/dev/repos/ahara-infra/infrastructure/terraform/control fmt -check project-harbor.tf
     terraform -chdir=/home/dev/repos/ahara-infra/infrastructure/terraform/services fmt -check db-migrate-truenas.tf
     terraform -chdir=/home/dev/repos/ahara-infra/infrastructure/terraform/network fmt -check locals.tf
     git -C /home/dev/repos/ahara-infra status --short
     ```

7. Produce an ahara-infra Terraform plan showing M1 changes [depends on #2, #3, #4, #5, #6]
   - File(s): `/home/dev/repos/ahara-infra/infrastructure/terraform/**` touched by prior steps.
   - Reference behavior: M1 exit requires planned DB and deployer changes visible in Terraform plan, with no Harbor reverse-proxy route. Terraform/AWS commands need credentials and must use `with-cred --`.
   - Change: No source changes. Run a plan from the ahara-infra Terraform root with credentials. Use the existing backend and state; do not apply.
   - Verify: Red if Terraform cannot plan or M1 resources are absent; green when plan output references Harbor deployer/SSM policy and TrueNAS DB registry/Lambda environment change, and does not reference a Harbor reverse-proxy route:
     ```bash
     cd /home/dev/repos/ahara-infra
     with-cred -- terraform -chdir=infrastructure/terraform init -reconfigure \
       -backend-config="bucket=${STATE_BUCKET:-tfstate-559098897826}" \
       -backend-config="region=${STATE_REGION:-us-east-1}" \
       -backend-config="use_lockfile=true"
     with-cred -- terraform -chdir=infrastructure/terraform plan -out=/tmp/harbor-m1.tfplan
     with-cred -- terraform -chdir=infrastructure/terraform show -no-color /tmp/harbor-m1.tfplan | tee /tmp/harbor-m1-plan.txt
     grep -q 'harbor' /tmp/harbor-m1-plan.txt
     grep -q 'truenas' /tmp/harbor-m1-plan.txt
     ! grep -q 'harbor.services.ahara.io' /tmp/harbor-m1-plan.txt
     ```

8. Run final Harbor and ahara-infra exit checks [depends on #7]
   - File(s): Harbor repo, `/home/dev/repos/ahara-infra` touched files.
   - Reference behavior: M1 exit requires Harbor `make ci` green plus ahara-infra formatting/checks green. Ahara-infra full `make ci` is the repo canonical check; it may be heavier but M1 exit calls for infra checks.
   - Change: No source changes.
   - Verify:
     ```bash
     cd /home/dev/repos/harbor
     make ci
     cd /home/dev/repos/ahara-infra
     make ci
     terraform fmt -check -recursive infrastructure/terraform/
     ```

## M1 Decision Register

| Step | Decision you own |
| ---- | ---- |
| None | M1 has no user-owned semantic decisions if port `30091` remains unused in ahara-infra network routes and Harbor compose binds `192.168.66.3:30091:80`. |

## Handoff

Execute only these M1 steps next. Do not apply Terraform. After M1 exits, return to [HARBOR-PLAN.md](HARBOR-PLAN.md) and run `plan-phase` on M2 before starting persistence work.
