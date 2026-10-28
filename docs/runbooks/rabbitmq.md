# RabbitMQ

OpenStack services use RabbitMQ, clustered across the controllers, for RPC and
notifications.

```bash
sudo docker exec rabbitmq rabbitmqctl cluster_status
sudo docker exec rabbitmq rabbitmq-diagnostics alarms
sudo docker exec rabbitmq rabbitmqctl list_queues name messages consumers | sort -k2 -n | tail
```

## RabbitMQDown

**Meaning.** Prometheus can't scrape RabbitMQ's metrics endpoint on a node for
2 minutes.

**Impact.** Clients reconnect to the surviving nodes. RPC calls in flight on
the failed node may time out, and API calls fail intermittently while that
happens.

**Diagnose.** Check `docker ps -a --filter name=rabbitmq`, then
`docker logs --tail 100 rabbitmq` and `/var/log/kolla/rabbitmq/`.

**Mitigate.** Run `docker start rabbitmq`, then confirm the node is listed
under running nodes in `cluster_status`. If the cluster is partitioned (several
nodes each report a different running set), restart the minority side's
`rabbitmq` containers one at a time.

## RabbitMQResourceAlarm

**Meaning.** A node crossed its memory high-watermark or free-disk limit.

**Impact.** RabbitMQ **blocks every publisher in the cluster** until the alarm
clears. OpenStack RPC stalls: instances get stuck in `BUILD` and API calls
time out.

**Diagnose.** Run the `list_queues` command above. A queue with many messages
and no consumers is the usual cause, often a service whose consumer has died.
Check free disk with `df -h /var/lib/docker`.

**Mitigate.**

- **A queue with no consumers.** Restart the service that consumes it, for
  example `docker restart nova_conductor`.
- **Notification queues piling up because nothing reads them.** Disable those
  notifications in that service's config through Kolla, rather than purging
  the queues over and over.
- **Disk.** Free space on the volume backing `/var/lib/docker`; see
  [NodeFilesystemAlmostFull](node-health.md#nodefilesystemalmostfull).
