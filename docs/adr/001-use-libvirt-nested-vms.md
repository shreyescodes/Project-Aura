# ADR 001: Model the platform on libvirt VMs with nested virtualisation

## Status

Accepted

## Context

The target topology has 3 controllers, 2 compute nodes and 3 Ceph nodes,
connected by four separate networks (management, external, tunnel, storage).
The HA behaviour that matters most includes keepalived failover, Galera
quorum, RabbitMQ clustering, Ceph replication and OVN's distributed
floating IPs. It only shows up with real multi-node networking.

Dedicated hardware at this scale isn't available for development. Yet a
single-node all-in-one deployment would hide most of the failure modes the
platform is designed to handle.

## Decision

Provision every node as a KVM guest on one hypervisor, using Terraform and the
`dmacvicar/libvirt` provider:

- Each logical network is its own libvirt bridge. The tunnel and storage
  networks are isolated and use jumbo frames.
- Compute nodes use `host-passthrough` CPUs so they can run KVM guests
  themselves (nested virtualisation).
- Ceph nodes get dedicated virtual disks for OSDs.

## Alternatives considered

- **All-in-one (single node).** Cheap, but nothing to fail over to. HA
  configuration is never exercised.
- **Public cloud VMs.** Most providers block nested virtualisation or charge a
  premium for it, and don't allow arbitrary L2 segments for provider networks.
- **Vagrant.** Workable, but adds a second provisioning tool alongside
  Terraform without adding anything.

## Consequences

- Multi-node control plane behaviour can be tested, including failure
  injection (stop a controller VM, pull a NIC).
- The Ansible roles and Kolla configuration are the same as for bare metal.
  Only the Terraform layer is lab-specific.
- Nested virtualisation is slower: tenant VMs boot more slowly, and Ceph
  latency is higher than on dedicated disks.
- The host needs about 72 GB of RAM at the default sizing (each group's size
  is a Terraform variable). A smaller host can run a reduced topology.
- The hypervisor is a single point of failure for the whole lab. This is
  acceptable for a lab and listed under known gaps in the architecture doc.
