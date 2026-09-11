# Project Aura: Private Cloud Platform

Welcome to **Project Aura**, a production-grade, multi-tenant private cloud platform based on OpenStack. This repository contains the Infrastructure as Code (IaC), configuration management, and custom platform services to deploy and manage a highly available OpenStack environment.

## Architecture
The platform is designed to be highly available and isolated:
- **Control Plane**: 3-node HA deployment (HAProxy, Keepalived, Galera DB, RabbitMQ).
- **Compute Plane**: 2+ KVM hypervisors for tenant workloads.
- **Storage Backend**: 3+ Ceph OSD nodes providing block (Cinder) and image (Glance) storage.
- **Networking**: OVN/OVS with tenant VLAN isolation (Management, External, Tunnel, Storage).

## Repository Structure
This repository follows standard software engineering practices for infrastructure projects:

- `terraform/`: Infrastructure provisioning (libvirt/OpenStack providers).
- `ansible/`: Configuration management (Kolla-Ansible, OS hardening, Ceph deploy).
- `api/`: Custom FastAPI platform services for tenant onboarding and management.
- `monitoring/`: Prometheus alerts and Grafana dashboards.
- `docs/`: Architecture Decision Records (ADRs) and Incident Runbooks.
- `argocd/`: GitOps manifests for Kubernetes-based continuous deployment (if applicable).
- `.github/workflows/`: CI/CD pipelines.

## Getting Started

### Prerequisites
- [Terraform](https://developer.hashicorp.com/terraform/downloads) (>= 1.6.0)
- [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html) (>= 2.16.0)
- `libvirt` / KVM (for local testing/simulation)

### Provisioning Infrastructure
```bash
# Initialize and apply Terraform
cd terraform/environments/production
terraform init
terraform plan
terraform apply
```

### Configuration (Ansible)
```bash
cd ansible
ansible-playbook -i inventories/production/hosts.yml playbooks/site.yml
```

## Contributing
1. Ensure `pre-commit` is installed and run `pre-commit install`.
2. Review the ADRs in `docs/adr/` before making architectural changes.
3. Submit a Pull Request. CI will validate Terraform formatting and Ansible linting.

## License
MIT
