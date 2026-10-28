# ADR 004: Static addressing and a Terraform-generated inventory

## Status

Accepted

## Context

The first version used libvirt DHCP with `wait_for_lease`. Three problems
followed:

- Addresses were only known after the VMs booted, so Terraform plans showed
  them as unknown.
- `wait_for_lease` stalled the apply whenever a lease was slow to appear.
- Addresses could change between rebuilds, while the Ansible inventory had to
  be maintained by hand.

Interface names inside the guests (`ens3`, `ens4`, ...) also depend on PCI
enumeration order. Kolla's `globals.yml` names interfaces explicitly, so
unstable names are fragile there.

## Decision

- **Static addresses.** Disable DHCP on every libvirt network. Node `i` of a
  group gets `cidrhost(cidr, offset + i)`, where each group owns a block of 10
  host numbers.
- **Stable NIC names.** Give every NIC a deterministic MAC,
  `52:54:00:<group>:<nic>:<node>`. Generate a cloud-init netplan config that
  matches on that MAC and renames the NIC after its role (`mgmt`, `tunnel`,
  `storage`, `external`).
- **Generated inventory.** Terraform writes the Ansible inventory, including
  each host's per-network addresses and the addressing plan, to
  `ansible/inventories/lab/hosts.yml`. The file is gitignored.

## Alternatives considered

- **Hand-maintained static inventory.** Simple, but duplicates the addressing
  plan, which then drifts.
- **Dynamic inventory plugin querying libvirt.** Reports domains, not the
  role-to-address mapping, and adds a runtime dependency on the hypervisor
  connection.

## Consequences

- Plans show every address, and `terraform apply` never waits on DHCP.
- Terraform is the single source of truth for addressing.
- Ansible can't run until Terraform has been applied, because the inventory
  doesn't exist before that. CI lints playbooks without an inventory.
- A group can have at most 9 nodes without changing the offsets.
