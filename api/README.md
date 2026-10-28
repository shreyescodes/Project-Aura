# Aura Platform API

Self-service tenant onboarding for the Aura OpenStack cloud. One API call turns
a tenant request into a ready-to-use OpenStack project:

1. A Keystone project, tagged `aura-managed` and with its tier.
2. Compute, block storage and network quotas for that tier.
3. A private network and subnet, with a router uplinked to the provider network.
4. The `member` role for each listed user.

If any step fails, the steps already done are rolled back, so a retry starts
from a clean slate. Offboarding is refused while the tenant still owns servers
or volumes.

## API

| Method   | Path                  | Purpose                                       |
|----------|-----------------------|-----------------------------------------------|
| `GET`    | `/v1/tenants`         | List managed tenants                          |
| `POST`   | `/v1/tenants`         | Onboard a tenant (`201`, `Location` header)   |
| `GET`    | `/v1/tenants/{name}`  | Tenant details, including its network         |
| `PATCH`  | `/v1/tenants/{name}`  | Change description or tier (re-applies quotas) |
| `DELETE` | `/v1/tenants/{name}`  | Offboard (`409` while resources remain)       |
| `GET`    | `/healthz`            | Liveness                                      |
| `GET`    | `/readyz`             | Readiness (Keystone reachable)                |
| `GET`    | `/metrics`            | Prometheus metrics                            |

`/v1` routes require an `X-API-Key` header. Every error response is an
[RFC 9457](https://www.rfc-editor.org/rfc/rfc9457) `application/problem+json`
body. The OpenAPI schema is served at `/docs`.

```bash
curl -sX POST localhost:8080/v1/tenants \
  -H 'X-API-Key: change-me' -H 'Content-Type: application/json' \
  -d '{"name": "acme-analytics", "tier": "medium", "members": ["alice"]}'
```

### Tiers

| Tier     | Instances | vCPUs | RAM (GiB) | Volumes | Storage (GiB) | Floating IPs |
|----------|----------:|------:|----------:|--------:|--------------:|-------------:|
| `small`  | 10        | 20    | 40        | 10      | 500           | 2            |
| `medium` | 25        | 50    | 100       | 25      | 2,000         | 5            |
| `large`  | 100       | 200   | 400       | 100     | 10,000        | 20           |

The full quota sets are defined in [`domain.py`](src/aura_api/domain.py).

## Design

```
routes/        HTTP layer: validation, status codes, auth
services/      Tenant lifecycle and rollback; no OpenStack types
cloud/         CloudGateway protocol + openstacksdk implementation
```

The service layer depends only on the `CloudGateway` protocol. Tests run it
against an in-memory fake (`tests/fakes.py`) and test the openstacksdk adapter
separately with a mocked connection, so no test needs a live cloud.

Ownership is enforced with tags: the API only lists, changes or deletes projects
tagged `aura-managed`. A project created by hand is reported as `404`.

Handlers are synchronous because openstacksdk is blocking; FastAPI runs them in
its worker thread pool. See [ADR 005](../docs/adr/005-synchronous-tenant-onboarding.md)
for why onboarding is synchronous rather than queued.

## Configuration

All settings come from `AURA_*` environment variables; see
[`.env.example`](.env.example). OpenStack credentials come from a `clouds.yaml`
entry (`AURA_OS_CLOUD`), which openstacksdk looks for in `./`,
`~/.config/openstack/` and `/etc/openstack/`.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync                      # create .venv from uv.lock
uv run pytest                # tests + coverage (fails under 90%)
uv run ruff check .          # lint
uv run ruff format .         # format
uv run mypy src tests        # strict type checking
uv run uvicorn aura_api.main:app --reload --port 8080
```

## Container

```bash
docker build -t aura-api .
docker run --rm -p 8080:8080 --env-file .env \
  -v /etc/kolla/clouds.yaml:/etc/openstack/clouds.yaml:ro aura-api
```

The image runs as an unprivileged user and contains only the runtime
virtualenv.
