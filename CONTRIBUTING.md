# Contributing

## Setup

```bash
pip install pre-commit && pre-commit install
cd api && uv sync                      # API toolchain (ruff, mypy, pytest)
```

The pre-commit hooks run the same checks as CI: formatting, Terraform
validate and TFLint, ansible-lint, yamllint, and ruff.

## Workflow

1. Branch from `main`: `feat/…`, `fix/…`, `docs/…` or `chore/…`.
2. Keep changes focused. Infrastructure and API changes go in separate pull
   requests.
3. Use [Conventional Commits](https://www.conventionalcommits.org/) for commit
   messages, for example `feat(api): add tenant tier downgrade check` or
   `fix(ceph): wait for OSDs before creating pools`.
4. Run `make lint test` before pushing, then open a pull request. CI must pass
   before merge.

## Conventions

- **Terraform.** Each module has `main.tf`, `variables.tf`, `outputs.tf` and
  `versions.tf`. Every variable and output has a description and a type.
  Provider versions are pinned in `.terraform.lock.hcl`; after changing a
  constraint, update the lock file for all platforms with
  `terraform providers lock -platform=linux_amd64 -platform=darwin_arm64 -platform=windows_amd64`.
- **Ansible.** Code must pass the `production` profile of ansible-lint. Role
  variables are prefixed with the role name. Inventory-wide facts written by
  Terraform use the `aura_` prefix. Tasks must be idempotent: use `creates:`,
  check state before acting, and set an honest `changed_when`.
- **Alerting rules.** Every alert needs a `runbook_url` pointing at a section
  in `docs/runbooks/`, and a promtool test for its firing condition.
- **API.** New behaviour needs tests. Coverage must stay above 90%, and
  `mypy --strict` must stay clean. Keep openstacksdk calls inside
  `cloud/openstack.py`.
- **Architecture changes.** Significant decisions get an ADR in `docs/adr/`.
  Start from the template.

## Upgrading pinned versions

Dependabot opens weekly pull requests for GitHub Actions, the API's Python
dependencies and the API's Docker base image. OpenStack and Ceph releases are
pinned in `ansible/inventories/lab/group_vars/all.yml`. Bump them in a
dedicated pull request that follows the upstream upgrade notes.
