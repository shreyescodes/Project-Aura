# Ceph

Run these on `ceph-0`, which holds the admin keyring:

```bash
sudo ceph -s
sudo ceph health detail
sudo ceph osd tree
sudo ceph orch ps
```

## CephHealthError

**Meaning.** The cluster has been in `HEALTH_ERR` for 5 minutes.

**Impact.** Depends on the cause. Inactive or down placement groups block I/O,
which freezes VMs and volume operations.

**Diagnose.** `ceph health detail` names the failing checks. Common ones:
`PG_AVAILABILITY` (inactive PGs), `OSD_FULL` and `MON_DOWN` with quorum lost.

**Mitigate.** Fix the check that `health detail` reports. Restoring
availability comes first: bring OSDs back, or free space (see
[CephClusterNearFull](#cephclusternearfull)). Don't mark OSDs `out` while PGs
are inactive unless you have checked that replicas exist elsewhere.

## CephHealthWarning

**Meaning.** The cluster has been in `HEALTH_WARN` for 30 minutes. Shorter
warnings, such as during recovery, are ignored on purpose.

**Diagnose.** Run `ceph health detail`.

**Mitigate.** Usually not urgent. Fix the cause, or if it is understood and
accepted, mute it with `ceph health mute <CODE> <duration>`, so the alert
stops masking new problems.

## CephOSDDown

**Meaning.** An OSD has been down for 5 minutes. The `ceph_daemon` label names
it.

**Impact.** Data on that OSD is degraded. Ceph re-replicates it once the OSD
is marked `out`, after 10 minutes by default.

**Diagnose.**

```bash
sudo ceph osd tree down
sudo ceph orch ps --daemon-type osd | grep <id>
sudo cephadm logs --name osd.<id>          # on the host that owns the OSD
```

**Mitigate.** If the daemon crashed, run
`ceph orch daemon restart osd.<id>`. If the disk has failed, replace it:
`ceph orch osd rm <id> --replace`, swap the device, and the OSD service spec
recreates the OSD on the new disk.

## CephMonitorOutOfQuorum

**Meaning.** A monitor has been out of quorum for 5 minutes.

**Impact.** The cluster keeps running while a majority of monitors (2 of 3)
are in quorum. One more failure stops all I/O.

**Diagnose.** Run `ceph quorum_status -f json-pretty` and
`ceph orch ps --daemon-type mon`. Clock skew is a frequent cause:
`ceph time-sync-status`.

**Mitigate.** Fix clock skew first (see
[NodeClockSkew](node-health.md#nodeclockskew)), then
`ceph orch daemon restart mon.<host>`.

## CephClusterNearFull

**Meaning.** Raw capacity is more than 75% used. Ceph itself warns at 85%
(`nearfull`) and stops writes at 95% (`full`).

**Impact.** None yet. This alert gives time to add capacity before writes stop.

**Diagnose.** Run `ceph df` and `ceph osd df tree`. Uneven OSD use points to a
balancing problem rather than a capacity one.

**Mitigate.** Add OSDs. In the lab, add entries to `data_disk_sizes_gib` and
re-apply Terraform; the OSD service spec consumes the new disks. Delete unused
Glance images and old snapshots. Check that the `balancer` module is on:
`ceph balancer status`.
