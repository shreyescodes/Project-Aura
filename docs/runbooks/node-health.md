# Node health

## NodeExporterDown

**Meaning.** Prometheus hasn't been able to scrape node-exporter on a host for
5 minutes.

**Impact.** No host metrics from that node. Often the whole node is down.

**Diagnose.**

```bash
ansible <host> -m ansible.builtin.ping          # from the ansible/ directory
ssh ubuntu@<host> 'sudo docker ps --filter name=prometheus_node_exporter'
virsh list --all | grep <host>                  # on the hypervisor (lab)
```

**Mitigate.** If the node is up but the container is stopped, run
`docker start prometheus_node_exporter`. If the node is down, start it with
`virsh start aura-<host>` and check the other alerts for the services it
hosts.

## NodeFilesystemAlmostFull

**Meaning.** A writable filesystem has had less than 10% free space for 15
minutes.

**Impact.** When `/var/lib/docker` fills up, containers can't write logs or
state. MariaDB and RabbitMQ stop accepting writes.

**Diagnose.**

```bash
df -h
sudo du -xh /var/log/kolla --max-depth=1 | sort -h | tail
sudo docker system df
```

**Mitigate.** Rotate or compress large logs under `/var/log/kolla`. Remove
unused images with `docker image prune`, after checking nothing still needs
them. On VMs, grow the disk by raising `os_disk_size_gib` and re-applying
Terraform.

## NodeMemoryPressure

**Meaning.** Less than 10% of memory has been available for 15 minutes.

**Impact.** The OOM killer may terminate containers. On computes, this hits
tenant VMs first.

**Diagnose.**

```bash
free -m
sudo docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}' | sort -k2 -h
```

**Mitigate.** On computes, stop scheduling new VMs by disabling the service
(`openstack compute service set --disable <host> nova-compute`) and migrate
instances away. On controllers, look for a runaway service. RabbitMQ queue
growth is a common cause; see [RabbitMQ](rabbitmq.md).

## NodeClockSkew

**Meaning.** The node's clock is more than 50 ms off from its NTP sources.

**Impact.** Ceph monitors report `MON_CLOCK_SKEW` and can lose quorum. Galera
and Keystone token validation also become unreliable.

**Diagnose.**

```bash
chronyc tracking
chronyc sources -v
```

**Mitigate.** Check that the NTP servers in `common_ntp_servers` can be reached
from the management network. Force a step with `sudo chronyc makestep`. If it
keeps happening, point every node at the same internal NTP source.
