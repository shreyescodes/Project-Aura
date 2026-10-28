# OpenStack services

```bash
source /etc/kolla/admin-openrc.sh
openstack compute service list
openstack network agent list
openstack volume service list
```

## OpenStackAPIDown

**Meaning.** openstack-exporter has failed to call a service's API through the
internal VIP for 5 minutes. The `service` label names the API.

**Impact.** Users and other services can't use that API. If Keystone is down,
every API is effectively down.

**Diagnose.**

1. Check whether the VIP is up and which controller holds it:
   `ip -br addr | grep <vip>` on each controller.
2. Check the backend containers:
   `docker ps -a --filter name=<service>_api` (Keystone runs as `keystone`).
3. Read the service log in `/var/log/kolla/<service>/`.
4. If several APIs are down at once, look for a shared cause first:
   [Galera](galera.md), [RabbitMQ](rabbitmq.md) or HAProxy.

**Mitigate.** Restart the failed container. If it fails again on start,
re-render its configuration with
`kolla-ansible reconfigure -i /etc/kolla/multinode --tags <service>`.

## HAProxyBackendDown

**Meaning.** An HAProxy backend has had no healthy servers for 2 minutes.

**Impact.** The service behind it is unreachable through the VIP.

**Diagnose.**

```bash
echo "show stat" | sudo socat stdio /var/lib/kolla/haproxy/haproxy.sock \
  | cut -d, -f1,2,18,37 | column -s, -t | grep -v UP
```

Then treat it as [OpenStackAPIDown](#openstackapidown) for that service.

**Mitigate.** Bring at least one backend container back. HAProxy health
checks re-add it automatically.

## NovaServiceDown

**Meaning.** An enabled Nova service (usually `nova-compute`) has stopped
reporting for 5 minutes.

**Impact.** New instances aren't scheduled to that host. Existing instances
keep running but can't be managed: no reboot, resize or migration.

**Diagnose.** Check `docker logs --tail 100 nova_compute` on the host. A failed
connection to RabbitMQ or libvirt is the usual cause, so also check
`docker ps --filter name=nova_libvirt`.

**Mitigate.** Restart `nova_libvirt`, then `nova_compute`. If the host is gone
for good, disable the service and evacuate its instances:
`openstack server evacuate` (instance disks are on Ceph, so evacuation keeps
the data).

## CinderServiceDown

**Meaning.** An enabled Cinder service has stopped reporting for 5 minutes.

**Impact.** No volumes can be created, attached or deleted through the down
`cinder-volume`. Volumes already attached keep working, because I/O goes
directly to Ceph.

**Diagnose.** Check `docker logs --tail 100 cinder_volume`. Ceph connectivity
errors point to [Ceph](ceph.md) or the keyring in
`/etc/kolla/config/cinder/cinder-volume/`.

**Mitigate.** Restart `cinder_volume`. If the keyring was rotated, re-run
`make openstack-config` and then
`kolla-ansible reconfigure --tags cinder`.

## NeutronAgentDown

**Meaning.** A Neutron agent (with OVN, the OVN controller or metadata agent)
is administratively up but not alive.

**Impact.** New ports on that host aren't wired up, so new VMs there have no
network. Existing flows usually keep working.

**Diagnose.** Check `docker ps --filter name=ovn` and
`docker logs ovn_controller` on the host. Make sure the tunnel interface is up
with MTU 9000: `ip -br link show tunnel`.

**Mitigate.** Restart `ovn_controller`, then `neutron_ovn_metadata_agent`.
