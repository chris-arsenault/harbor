# 0001 - TrueNAS Platform Deployment

- Status: Accepted
- Date: 2026-06-16

## Context

Harbor is a long-running trading research service that needs WebSocket observability, local database state, and controlled access to secrets. The Ahara platform already provides shared CI, GHCR publishing, Komodo deployment, SSM-backed TrueNAS secrets, and TrueNAS PostgreSQL registration. The product specification keeps the UI off the public internet, reachable only through the LAN or VPN.

## Decision

Harbor deploys as an Ahara TrueNAS LAN service with separate backend and frontend images, `compose.yaml`, `secret-paths.yml`, Komodo deployment, and TrueNAS PostgreSQL. The frontend publishes `192.168.66.3:30091:80` from compose, following Sulion's LAN-only TrueNAS pattern. Harbor does not register a `reverse_proxy_routes` entry in Ahara M1.

## Alternatives considered

- **Standalone local Docker Compose** - simpler for first boot, but bypasses the platform's deployment, secret, and database controls.
- **AWS Lambda plus shared RDS** - fits standard Ahara HTTP apps, but does not fit a 24/5 streaming trading process or local TrueNAS service requirement.
- **Single combined image** - fewer deploy artifacts, but couples the backend runtime and frontend static serving and makes operational health less clear.

## Consequences

The implementation must include Ahara platform files from the start. Deployment work includes coordinated changes in `ahara-infra` for the deployer role and TrueNAS database registration. Dockerfiles package deployable artifacts for the platform workflow, secrets enter the stack through SSM paths rather than committed environment values, and deployed access is verified on the LAN endpoint instead of an internet-facing route.
