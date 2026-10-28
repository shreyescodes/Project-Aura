# Runbooks

Every Prometheus alert has a `runbook_url` that links to a section below. Each
section covers what the alert means, its impact, how to diagnose it and how to
mitigate it.

| Runbook | Alerts |
|---------|--------|
| [Node health](node-health.md) | NodeExporterDown, NodeFilesystemAlmostFull, NodeMemoryPressure, NodeClockSkew |
| [Galera](galera.md) | MariaDBDown, GaleraNodeNotSynced, GaleraClusterSizeReduced |
| [RabbitMQ](rabbitmq.md) | RabbitMQDown, RabbitMQResourceAlarm |
| [OpenStack services](openstack-services.md) | OpenStackAPIDown, HAProxyBackendDown, NovaServiceDown, CinderServiceDown, NeutronAgentDown |
| [Ceph](ceph.md) | CephHealthError, CephHealthWarning, CephOSDDown, CephMonitorOutOfQuorum, CephClusterNearFull |

## Conventions

- **Where to run commands.** OpenStack CLI commands run on the deployment host
  (`controller-0`) after `source /etc/kolla/admin-openrc.sh`. `ceph` commands
  run on `ceph-0`, which holds the admin keyring.
- **Kolla services.** Each service runs as a Docker container named after it
  (`mariadb`, `rabbitmq`, `nova_compute`, ...). Logs are in
  `/var/log/kolla/<service>/` on the host.
- **Configuration changes.** Make them through this repository and redeploy.
  A hand edit inside a container is lost on the next deploy.
