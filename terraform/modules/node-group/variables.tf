variable "name" {
  description = "Role name of the group. Nodes are named <name>-0, <name>-1, and so on."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,30}$", var.name))
    error_message = "name must be a lowercase DNS label (letters, digits, hyphens)."
  }
}

variable "name_prefix" {
  description = "Prefix for libvirt object names (domains, volumes). Guest hostnames are not prefixed."
  type        = string
  default     = "aura"
}

variable "node_count" {
  description = "Number of nodes in the group."
  type        = number

  validation {
    condition     = var.node_count >= 0 && var.node_count <= 9 && floor(var.node_count) == var.node_count
    error_message = "node_count must be a whole number from 0 to 9 (each group owns a block of 10 addresses)."
  }
}

variable "vcpu" {
  description = "vCPUs per node."
  type        = number
}

variable "memory_mib" {
  description = "Memory per node, in MiB."
  type        = number
}

variable "cpu_mode" {
  description = "libvirt CPU mode. host-passthrough exposes VT-x/AMD-V so guests can run KVM themselves."
  type        = string
  default     = "host-passthrough"
}

variable "os_disk_size_gib" {
  description = "Size of the OS disk, in GiB. The base image is grown to this size on first boot."
  type        = number
}

variable "data_disk_sizes_gib" {
  description = "Sizes of additional blank disks per node, in GiB (for example Ceph OSD devices)."
  type        = list(number)
  default     = []
}

variable "base_volume_id" {
  description = "ID of the libvirt volume holding the cloud image that OS disks are cloned from."
  type        = string
}

variable "storage_pool" {
  description = "libvirt storage pool for this group's volumes."
  type        = string
}

variable "admin_user" {
  description = "Login created by cloud-init with passwordless sudo and the given SSH keys."
  type        = string
}

variable "ssh_public_keys" {
  description = "SSH public keys authorised for admin_user."
  type        = list(string)
}

variable "dns_domain" {
  description = "DNS search domain for the nodes."
  type        = string
}

variable "nameservers" {
  description = "DNS resolvers configured on the interface that carries the default route."
  type        = list(string)
}

variable "mac_group_id" {
  description = "Byte (0-255) embedded in every MAC address of this group. Must be unique per group in an environment."
  type        = number

  validation {
    condition     = var.mac_group_id >= 0 && var.mac_group_id <= 255
    error_message = "mac_group_id must be between 0 and 255."
  }
}

variable "address_offset" {
  description = "Host number of the first node in every subnet. Node i gets cidrhost(cidr, address_offset + i)."
  type        = number
}

variable "interfaces" {
  description = <<-EOT
    NICs attached to every node, in PCI order.
      name              - guest interface name (netplan set-name), for example "mgmt".
      network_id        - libvirt network to attach.
      cidr / mtu        - subnet and MTU of that network.
      configure_address - false leaves the NIC up without an IP (used for Neutron's external bridge).
      gateway           - when set, the default route and DNS resolvers go through this NIC.
  EOT
  type = list(object({
    name              = string
    network_id        = string
    cidr              = string
    mtu               = number
    configure_address = optional(bool, true)
    gateway           = optional(string)
  }))

  validation {
    condition     = length([for i in var.interfaces : i if i.gateway != null]) <= 1
    error_message = "At most one interface can carry the default gateway."
  }

  validation {
    condition     = alltrue([for i in var.interfaces : length(i.name) <= 15])
    error_message = "Linux interface names are limited to 15 characters."
  }
}
