locals {
  gib = 1024 * 1024 * 1024

  # Keyed by hostname rather than using count, so resource addresses read as
  # module.controllers.libvirt_domain.this["controller-0"] in plans.
  nodes = { for i in range(var.node_count) : "${var.name}-${i}" => i }

  # MAC 52:54:00:<group>:<nic>:<node> is unique per environment and lets netplan
  # match NICs by MAC, so interface naming never depends on PCI enumeration.
  node_interfaces = {
    for hostname, index in local.nodes : hostname => [
      for nic_index, nic in var.interfaces : {
        name          = nic.name
        network_id    = nic.network_id
        mtu           = nic.mtu
        gateway       = nic.gateway
        mac           = format("52:54:00:%02x:%02x:%02x", var.mac_group_id, nic_index, index)
        address       = nic.configure_address ? cidrhost(nic.cidr, var.address_offset + index) : null
        prefix_length = split("/", nic.cidr)[1]
      }
    ]
  }

  data_disks = merge([
    for hostname, _ in local.nodes : {
      for disk_index, size in var.data_disk_sizes_gib :
      "${hostname}-data${disk_index}" => { hostname = hostname, size_gib = size }
    }
  ]...)
}

resource "libvirt_volume" "os" {
  for_each = local.nodes

  name           = "${var.name_prefix}-${each.key}-os.qcow2"
  pool           = var.storage_pool
  base_volume_id = var.base_volume_id
  format         = "qcow2"
  size           = var.os_disk_size_gib * local.gib
}

resource "libvirt_volume" "data" {
  for_each = local.data_disks

  name   = "${var.name_prefix}-${each.key}.qcow2"
  pool   = var.storage_pool
  format = "qcow2"
  size   = each.value.size_gib * local.gib
}

resource "libvirt_cloudinit_disk" "this" {
  for_each = local.nodes

  name = "${var.name_prefix}-${each.key}-cloudinit.iso"
  pool = var.storage_pool

  meta_data = yamlencode({
    instance-id    = "${var.name_prefix}-${each.key}"
    local-hostname = each.key
  })

  # /etc/hosts is left to Ansible: cloud-init's manage_etc_hosts maps the
  # hostname to 127.0.1.1, which breaks Kolla's hostname resolution prechecks.
  user_data = join("\n", ["#cloud-config", yamlencode({
    hostname         = each.key
    fqdn             = "${each.key}.${var.dns_domain}"
    manage_etc_hosts = false
    timezone         = "UTC"
    ssh_pwauth       = false
    disable_root     = true
    users = [{
      name                = var.admin_user
      groups              = ["sudo"]
      shell               = "/bin/bash"
      sudo                = "ALL=(ALL) NOPASSWD:ALL"
      lock_passwd         = true
      ssh_authorized_keys = var.ssh_public_keys
    }]
    package_update = true
    packages       = ["qemu-guest-agent", "python3"]
    runcmd         = [["systemctl", "enable", "--now", "qemu-guest-agent"]]
  })])

  network_config = yamlencode({
    version = 2
    ethernets = {
      for nic in local.node_interfaces[each.key] : nic.name => {
        # Drop unset keys so netplan only sees what applies to this NIC.
        for key, value in {
          match     = { macaddress = nic.mac }
          set-name  = nic.name
          mtu       = nic.mtu
          dhcp4     = false
          dhcp6     = false
          accept-ra = false
          addresses = nic.address == null ? null : ["${nic.address}/${nic.prefix_length}"]
          routes    = nic.gateway == null ? null : [{ to = "default", via = nic.gateway }]
          nameservers = nic.gateway == null ? null : {
            addresses = var.nameservers
            search    = [var.dns_domain]
          }
        } : key => value if value != null
      }
    }
  })
}

resource "libvirt_domain" "this" {
  for_each = local.nodes

  name       = "${var.name_prefix}-${each.key}"
  vcpu       = var.vcpu
  memory     = var.memory_mib
  autostart  = true
  qemu_agent = true
  cloudinit  = libvirt_cloudinit_disk.this[each.key].id

  cpu {
    mode = var.cpu_mode
  }

  dynamic "network_interface" {
    for_each = local.node_interfaces[each.key]

    content {
      network_id = network_interface.value.network_id
      mac        = network_interface.value.mac
    }
  }

  disk {
    volume_id = libvirt_volume.os[each.key].id
  }

  dynamic "disk" {
    for_each = range(length(var.data_disk_sizes_gib))

    content {
      volume_id = libvirt_volume.data["${each.key}-data${disk.value}"].id
    }
  }

  console {
    type        = "pty"
    target_type = "serial"
    target_port = "0"
  }

  graphics {
    type           = "vnc"
    listen_type    = "address"
    listen_address = "127.0.0.1"
  }
}
