# ADR 003: Run Ceph as an external cluster managed by cephadm

## Status

Accepted

## Context

Glance, Cinder and Nova need shared storage so that VMs boot from
copy-on-write clones and can live-migrate. Kolla-Ansible removed its own Ceph
deployment in the Train release. Ceph is now expected to be deployed and run
separately.

## Decision

Deploy Ceph Squid with cephadm on dedicated storage nodes. Ansible:

1. Bootstraps the first node, setting the monitor IP on the storage network.
2. Enrolls the remaining nodes and labels them for MON/MGR placement.
3. Applies a declarative service spec, so every unused disk becomes an OSD.
4. Creates the `images`, `volumes` and `vms` pools, plus least-privilege
   `client.glance` and `client.cinder` keys.

The kolla role reads the minimal `ceph.conf` and keyrings from the Ceph admin
node and installs them where Kolla expects them. Kolla then configures the
OpenStack services as RBD clients.

## Alternatives considered

- **ceph-ansible.** Deprecated upstream in favour of cephadm.
- **Rook.** Requires a Kubernetes cluster.
- **LVM/iSCSI Cinder backend.** No copy-on-write image cloning, and no
  live migration without shared storage.

## Consequences

- Ceph and OpenStack upgrade on their own schedules. Ceph upgrades go through
  `ceph orch upgrade`.
- Monitoring comes from Kolla's Prometheus, which scrapes the MGR's Prometheus
  module. cephadm's own monitoring stack is skipped to avoid running two.
- The lab's storage nodes have little memory. OSD memory is autotuned by
  cephadm, and performance is not representative of production.
