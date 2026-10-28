# ADR 005: Synchronous tenant onboarding with compensating rollback

## Status

Accepted

## Context

Onboarding a tenant takes roughly ten OpenStack API calls: project, quotas
(three services), network, subnet, router, gateway, interface and role grants.
That usually adds up to a few seconds. A failure part-way through leaves
orphaned resources that block a retry. For example, the project name stays
taken.

The original scaffold listed Celery and Redis as dependencies for running this
as background jobs.

## Decision

Run onboarding synchronously within the request:

- Validate everything that can be checked up front (name format, CIDR, member
  users) before creating anything.
- Record an undo step after each successful step. On any failure, run the undo
  steps newest-first and return `502` with a problem body saying that the
  request was rolled back.
- Let Keystone's per-domain unique project names settle concurrent requests
  for the same tenant. The loser gets `409`.

Celery, Redis and the rate-limiter dependency were removed.

## Alternatives considered

- **Job queue (Celery + Redis).** Gives retries and progress tracking, but
  adds two services to deploy, monitor and secure. Clients would also have to
  poll a job resource. That cost isn't justified for an operation that takes
  seconds and is rare (a few tenants a week).
- **No rollback; rely on retries being idempotent.** Every step would have to
  adopt existing resources, which is harder to reason about. A failed request
  would also leave half-built tenants visible to users.

## Consequences

- The API stays stateless: one container, no broker, no database.
- Request latency includes the OpenStack calls. Handlers are synchronous and
  run in FastAPI's thread pool, so slow calls don't block the event loop.
- If the API process dies mid-request, rollback doesn't run. The partial
  tenant is still tagged `aura-managed`, so it is visible through the API and
  can be offboarded with `DELETE`. If onboarding volume grows, or
  long-running steps are added (such as image imports), revisit this ADR in
  favour of a job queue.
