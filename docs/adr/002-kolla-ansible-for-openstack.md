# ADR 002: Deploy OpenStack with Kolla-Ansible

## Status

Accepted

## Context

OpenStack consists of a dozen services, each with its own configuration,
database, message-queue user and HA requirements. Day-2 operations (upgrades,
adding compute nodes, reconfiguring a service) matter as much as the first
deploy.

## Decision

Use Kolla-Ansible to deploy containerised OpenStack services, pinned to a
stable release (`2025.1`, via `kolla_openstack_release`). This repository owns
the inputs: `globals.yml`, the inventory, Ceph credentials and alerting rules.
Kolla owns how the services are deployed.

The deployment host is the first controller. It runs Kolla-Ansible from a
virtualenv and reaches the other nodes with its own SSH key.

## Alternatives considered

- **OpenStack-Ansible.** Also mature, but deploys services into LXC containers
  with a heavier host footprint, and its defaults are less opinionated.
- **Manual or distro packages.** Every HA and upgrade path would have to be
  scripted by hand.
- **Kubernetes-based (OpenStack-Helm).** Adds a Kubernetes cluster to run and
  upgrade underneath OpenStack, with no clear benefit at this scale.

## Consequences

- Upgrades follow Kolla's supported path: bump the release, then run
  `kolla-ansible upgrade`.
- Service configuration is reproducible from this repository plus the
  generated passwords on the deployment host.
- Kolla's service-to-group mapping is copied from the installed release
  rather than kept in this repository, so it can't drift on upgrade. The role
  asserts the layout it expects.
- Debugging needs familiarity with Kolla's conventions: container names, logs
  under `/var/log/kolla`, and config under `/etc/kolla`.
