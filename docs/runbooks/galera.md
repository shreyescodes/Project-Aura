# Galera (MariaDB)

Every OpenStack service stores its state in a three-node MariaDB Galera
cluster on the controllers. HAProxy sends writes to one node at a time.

Check cluster state on any controller:

```bash
sudo docker exec mariadb mysql -uroot -p"$(sudo awk '/^database_password/ {print $2}' /etc/kolla/passwords.yml)" \
  -e "SHOW STATUS WHERE Variable_name IN ('wsrep_cluster_size','wsrep_cluster_status','wsrep_local_state_comment','wsrep_ready')"
```

The password is only in `passwords.yml` on the deployment host. On other
controllers, read it from there.

## MariaDBDown

**Meaning.** mysqld-exporter can't connect to the local MariaDB for 2 minutes.

**Impact.** The cluster keeps running on the remaining nodes. HAProxy stops
routing to the failed one. Losing a second node costs the cluster its quorum.

**Diagnose.** Check `docker ps -a --filter name=mariadb` and
`docker logs --tail 100 mariadb`, and look in `/var/log/kolla/mariadb/`.

**Mitigate.** If the container exited, start it with `docker start mariadb`.
It rejoins through IST or SST. Watch for `GaleraNodeNotSynced` to clear.

## GaleraNodeNotSynced

**Meaning.** `wsrep_local_state` hasn't been 4 (Synced) for 10 minutes. The
node is Joining, a Donor, or Desynced.

**Impact.** A long-running donor serves stale reads and slows writes across
the cluster.

**Diagnose.** Read `wsrep_local_state_comment` (query above) and check the
MariaDB log for an SST that is stuck or failing.

**Mitigate.** A stuck SST is usually a disk-space or network problem between
controllers. Fix that, then restart the joining node with
`docker restart mariadb`.

## GaleraClusterSizeReduced

**Meaning.** A node reports fewer than 3 cluster members for 5 minutes.

**Impact.** At 2 of 3 members the cluster still has quorum, but one more
failure takes it down. At 1 member, or a non-`Primary` status, the database is
read-only and **every OpenStack API fails**.

**Diagnose.** Run the status query on every controller. Find which nodes see
each other and whether any of them reports `wsrep_cluster_status = Primary`.

**Mitigate.**

- **One node out, cluster still `Primary`.** Restart MariaDB on the missing
  node.
- **No `Primary` component (full outage).** Use Kolla's recovery play, which
  finds the most advanced node and bootstraps from it:

  ```bash
  kolla-ansible mariadb_recovery -i /etc/kolla/multinode
  ```

  Don't bootstrap a node by hand unless you have confirmed it has the highest
  `seqno` in `/var/lib/docker/volumes/mariadb/_data/grastate.dat`.
