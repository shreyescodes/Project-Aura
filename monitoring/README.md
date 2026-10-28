# Monitoring

Kolla-Ansible deploys Prometheus, Alertmanager and Grafana on the controllers.
This directory holds the platform's own alerting rules. The `kolla` role copies
them into Kolla's custom config (`/etc/kolla/config/prometheus/*.rules`), so
they are loaded on every deploy or reconfigure.

| File | Covers |
|------|--------|
| `rules/node.rules.yml` | Exporter reachability, disk, memory, clock skew |
| `rules/control-plane.rules.yml` | Galera, RabbitMQ, HAProxy |
| `rules/openstack.rules.yml` | API reachability, Nova/Cinder services, Neutron agents |
| `rules/ceph.rules.yml` | Cluster health, OSDs, monitor quorum, capacity |

Every alert has a `severity` label (`critical` pages; `warning` goes to a
ticket queue) and a `runbook_url` that links to [`docs/runbooks`](../docs/runbooks).

## Testing

Each rule file has a promtool unit test in `prometheus/tests/`. The tests feed
synthetic series and assert exactly which alerts fire, with which labels and
annotations.

```bash
cd monitoring/prometheus
promtool check rules rules/*.yml
promtool test rules tests/*.test.yml
```

The `for:` durations and thresholds are tuned for the three-controller,
three-OSD-node lab. `GaleraClusterSizeReduced` hard-codes the expected cluster
size of 3.
