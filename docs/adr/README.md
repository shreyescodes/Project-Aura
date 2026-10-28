# Architecture Decision Records

Each ADR records one significant decision: its context, what was chosen and
what it costs. To propose a change, copy [`template.md`](template.md), take the
next number, and open a pull request. A decision that is reversed later stays
in place, marked `Superseded by ADR NNN`.

| ADR | Title | Status |
|-----|-------|--------|
| [001](001-use-libvirt-nested-vms.md) | Model the platform on libvirt VMs with nested virtualisation | Accepted |
| [002](002-kolla-ansible-for-openstack.md) | Deploy OpenStack with Kolla-Ansible | Accepted |
| [003](003-ceph-with-cephadm.md) | Run Ceph as an external cluster managed by cephadm | Accepted |
| [004](004-static-addressing-and-generated-inventory.md) | Static addressing and a Terraform-generated inventory | Accepted |
| [005](005-synchronous-tenant-onboarding.md) | Synchronous tenant onboarding with compensating rollback | Accepted |
