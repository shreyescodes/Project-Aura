# Project Aura

[![CI](https://github.com/shreyescodes/Project-Aura/actions/workflows/ci.yml/badge.svg)](https://github.com/shreyescodes/Project-Aura/actions/workflows/ci.yml)

Infrastructure-as-code for a highly available OpenStack private cloud, with
Ceph storage, monitoring and a self-service tenant onboarding API.

| Layer         | Tooling                     | What it builds |
|---------------|-----------------------------|----------------|
| Provisioning  | Terraform + libvirt         | 8 KVM nodes on 4 segmented networks, with static addressing |
| Configuration | Ansible                     | OS baseline and hardening, Ceph (cephadm), OpenStack (Kolla-Ansible 2025.1) |
| Platform      | Python / FastAPI            | Tenant onboarding API: projects, quotas, networks, role grants |
| Observability | Prometheus, Alertmanager, Grafana | Unit-tested alerting rules, each linked to a runbook |

| Nodes            | Run |
|------------------|-----|
| `controller-0..2` | OpenStack APIs behind HAProxy and a keepalived VIP, Galera, RabbitMQ, OVN central, Prometheus |
| `compute-0..1`   | nova-compute and libvirt (nested KVM), OVN chassis with distributed floating IPs |
| `ceph-0..2`      | Ceph MON, MGR and 2 OSDs each, serving the RBD pools `images`, `volumes` and `vms` |

The nodes are connected by four networks: `mgmt`, `external` (provider), `tunnel`
(Geneve) and `storage`.

See [docs/architecture.md](docs/architecture.md) for the design, the network
plan and known gaps against production. See [docs/adr/](docs/adr/) for the
decisions behind it.

## Repository layout

```
terraform/
  modules/networking/      libvirt networks (one per traffic class)
  modules/node-group/      KVM guests with static, MAC-matched NIC naming
  environments/lab/        composes the topology; writes the Ansible inventory
ansible/
  playbooks/               bootstrap → ceph → openstack (site.yml runs all three)
  roles/common/            OS baseline: hosts, NTP, sysctl, sshd hardening
  roles/ceph/              cephadm bootstrap, OSDs, OpenStack pools and keys
  roles/kolla/             Kolla-Ansible install, config, Ceph wiring, deploy
api/                       tenant onboarding service (FastAPI, uv, Docker)
monitoring/prometheus/     alerting rules and promtool unit tests
docs/                      architecture, ADRs, runbooks
```

## Deploying the lab

### Prerequisites

- **Hypervisor.** A Linux host with KVM and libvirt, nested virtualisation
  enabled, and about 72 GB of RAM at default sizing. Each group's size is a
  Terraform variable.
- **Tools.** Terraform >= 1.6, Ansible (ansible-core 2.16+), and `make`.

### Steps

```bash
# 1. Provision VMs and networks; this also writes ansible/inventories/lab/hosts.yml
cp terraform/environments/lab/terraform.tfvars.example terraform/environments/lab/terraform.tfvars
$EDITOR terraform/environments/lab/terraform.tfvars      # add your SSH public key
make infra-init infra-plan infra-apply

# 2. Configure everything: OS baseline, Ceph, then OpenStack (~1 hour)
make ansible-deps
make ping
make deploy

# 3. Use the cloud
ssh ubuntu@10.0.10.11
sudo -i && source /etc/kolla/admin-openrc.sh && openstack endpoint list
```

Each phase can be re-run on its own: `make bootstrap`, `make ceph`,
`make openstack-config` (render configuration only) and `make openstack`.
Run `make help` to list every target.

## Platform API

The onboarding service creates a tenant in one call: a project, tier-based
quotas, a routed private network and member role grants. If any step fails,
the steps already done are rolled back. For details, see
[api/README.md](api/README.md).

```bash
cd api && uv sync && uv run pytest
```

## Quality gates

Every pull request runs the following checks
([.github/workflows/ci.yml](.github/workflows/ci.yml)). The same checks run
locally through `make lint test` or pre-commit.

| Area       | Checks |
|------------|--------|
| Terraform  | `fmt`, `validate` against the committed lock file, TFLint (all rules) |
| Ansible    | ansible-lint, `production` profile |
| YAML       | yamllint (strict) |
| Monitoring | `promtool check rules` and `promtool test rules` |
| API        | ruff lint and format, mypy `--strict`, pytest with a 90% coverage floor, Docker build and smoke test |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
