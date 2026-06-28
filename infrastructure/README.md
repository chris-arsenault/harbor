# Infrastructure

Harbor owns project-local Terraform under `infrastructure/terraform/`.

The Terraform creates the Harbor Cognito app client in the shared Ahara user pool and publishes:

- `/ahara/cognito/clients/harbor-app`
- `/ahara/auth-trigger/clients/harbor`

Ahara integration also requires coordinated edits in `ahara-infra` for the deployer role, Cognito app permissions, auth-trigger parameter access, and TrueNAS database registration. Harbor is LAN-published from compose rather than registered in the Ahara reverse proxy.
