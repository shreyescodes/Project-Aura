# ADR 001: Use libvirt for Local/Nested Virtualization

## Status
Accepted

## Context
We are building a production-ready OpenStack platform for a learning project aiming at a senior platform engineer role. The target architecture requires:
- 3 Controller Nodes
- 2 Compute Nodes
- 3 Ceph Storage Nodes

Provisioning physical hardware for this scale is impractical for a local development or learning environment. However, the deployment needs to simulate a real multi-node architecture (VLANs, bonded NICs, multi-disk storage, high availability) as closely as possible to serve as a valid proof of concept for a production deployment.

## Decision
We will use Terraform with the `dmacvicar/libvirt` provider to provision the nodes as nested VMs on a local hypervisor. This allows us to accurately model the multi-node architecture and logical network separation using virtual networks and virtual disks. The compute nodes will have nested VT-x (`host-passthrough`) enabled so they can run KVM hypervisors themselves for tenant VMs.

## Consequences

### Positive
- Accurate simulation of multi-node control planes, enabling testing of HA components like HAProxy, Keepalived, RabbitMQ clustering, and Galera.
- Ability to simulate complex network topologies (Management, Tunnel, Storage, External) using virtual networks.
- Infrastructure provisioning remains fully automated via Terraform.
- Cost-effective local development.

### Negative
- Nested virtualization carries a performance penalty, which might impact the boot times of tenant VMs and storage performance (Ceph).
- Requires a host with substantial RAM (at least 32-64GB recommended to run all nodes comfortably) and KVM/QEMU setup.
