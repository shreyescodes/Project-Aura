locals {
  # Every node uses libvirt's dnsmasq on the management bridge as its resolver.
  nameservers = [module.networking.networks.mgmt.gateway]

  # NIC definitions shared by the node groups. Order is PCI order inside the guest.
  nic = {
    mgmt = {
      name       = "mgmt"
      network_id = module.networking.networks.mgmt.id
      cidr       = module.networking.networks.mgmt.cidr
      mtu        = module.networking.networks.mgmt.mtu
      gateway    = module.networking.networks.mgmt.gateway
    }
    tunnel = {
      name       = "tunnel"
      network_id = module.networking.networks.tunnel.id
      cidr       = module.networking.networks.tunnel.cidr
      mtu        = module.networking.networks.tunnel.mtu
    }
    storage = {
      name       = "storage"
      network_id = module.networking.networks.storage.id
      cidr       = module.networking.networks.storage.cidr
      mtu        = module.networking.networks.storage.mtu
    }
    # Handed to Neutron/OVN as the provider bridge port, so it must not carry an IP.
    external = {
      name              = "external"
      network_id        = module.networking.networks.external.id
      cidr              = module.networking.networks.external.cidr
      mtu               = module.networking.networks.external.mtu
      configure_address = false
    }
  }

  node_defaults = {
    name_prefix     = "aura"
    base_volume_id  = libvirt_volume.base.id
    storage_pool    = var.storage_pool
    admin_user      = var.admin_user
    ssh_public_keys = var.ssh_public_keys
    dns_domain      = var.dns_domain
  }
}

resource "libvirt_volume" "base" {
  name   = "aura-base-${basename(var.base_image_url)}"
  pool   = var.storage_pool
  source = var.base_image_url
  format = "qcow2"
}

module "networking" {
  source = "../../modules/networking"

  dns_domain = var.dns_domain
  networks   = var.networks
}

# Controllers also act as Neutron network nodes, so they need the tunnel and
# external NICs. They reach Ceph on the storage network for Glance and Cinder.
module "controllers" {
  source = "../../modules/node-group"

  name             = "controller"
  node_count       = var.controllers.count
  vcpu             = var.controllers.vcpu
  memory_mib       = var.controllers.memory_mib
  os_disk_size_gib = var.controllers.os_disk_size_gib
  mac_group_id     = 1
  address_offset   = 11
  interfaces       = [local.nic.mgmt, local.nic.tunnel, local.nic.storage, local.nic.external]

  name_prefix     = local.node_defaults.name_prefix
  base_volume_id  = local.node_defaults.base_volume_id
  storage_pool    = local.node_defaults.storage_pool
  admin_user      = local.node_defaults.admin_user
  ssh_public_keys = local.node_defaults.ssh_public_keys
  dns_domain      = local.node_defaults.dns_domain
  nameservers     = local.nameservers
}

# Computes get the external NIC too, because OVN distributed floating IPs
# send north-south traffic straight from the hypervisor.
module "computes" {
  source = "../../modules/node-group"

  name             = "compute"
  node_count       = var.computes.count
  vcpu             = var.computes.vcpu
  memory_mib       = var.computes.memory_mib
  os_disk_size_gib = var.computes.os_disk_size_gib
  mac_group_id     = 2
  address_offset   = 21
  interfaces       = [local.nic.mgmt, local.nic.tunnel, local.nic.storage, local.nic.external]

  name_prefix     = local.node_defaults.name_prefix
  base_volume_id  = local.node_defaults.base_volume_id
  storage_pool    = local.node_defaults.storage_pool
  admin_user      = local.node_defaults.admin_user
  ssh_public_keys = local.node_defaults.ssh_public_keys
  dns_domain      = local.node_defaults.dns_domain
  nameservers     = local.nameservers
}

module "ceph" {
  source = "../../modules/node-group"

  name                = "ceph"
  node_count          = var.ceph.count
  vcpu                = var.ceph.vcpu
  memory_mib          = var.ceph.memory_mib
  os_disk_size_gib    = var.ceph.os_disk_size_gib
  data_disk_sizes_gib = var.ceph.data_disk_sizes_gib
  cpu_mode            = "host-model"
  mac_group_id        = 3
  address_offset      = 31
  interfaces          = [local.nic.mgmt, local.nic.storage]

  name_prefix     = local.node_defaults.name_prefix
  base_volume_id  = local.node_defaults.base_volume_id
  storage_pool    = local.node_defaults.storage_pool
  admin_user      = local.node_defaults.admin_user
  ssh_public_keys = local.node_defaults.ssh_public_keys
  dns_domain      = local.node_defaults.dns_domain
  nameservers     = local.nameservers
}
