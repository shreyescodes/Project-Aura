output "nodes" {
  description = "Nodes keyed by hostname. addresses maps interface name to IPv4 address (unaddressed NICs are omitted)."
  value = {
    for hostname, _ in local.nodes : hostname => {
      domain_id = libvirt_domain.this[hostname].id
      addresses = {
        for nic in local.node_interfaces[hostname] : nic.name => nic.address if nic.address != null
      }
    }
  }
}
