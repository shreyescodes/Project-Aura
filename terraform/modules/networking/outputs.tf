output "networks" {
  description = "Created networks keyed by logical name. gateway is the hypervisor's address on that bridge."
  value = {
    for key, network in libvirt_network.this : key => {
      id      = network.id
      name    = network.name
      cidr    = var.networks[key].cidr
      gateway = cidrhost(var.networks[key].cidr, 1)
      mtu     = var.networks[key].mtu
      mode    = var.networks[key].mode
    }
  }
}
