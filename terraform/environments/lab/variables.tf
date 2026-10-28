variable "libvirt_uri" {
  description = "libvirt connection URI. Use qemu+ssh://user@host/system to provision a remote hypervisor."
  type        = string
  default     = "qemu:///system"
}

variable "storage_pool" {
  description = "Existing libvirt storage pool for all volumes."
  type        = string
  default     = "default"
}

variable "base_image_url" {
  description = "URL or local path of the Ubuntu cloud image that every node boots from."
  type        = string
  default     = "https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img"
}

variable "admin_user" {
  description = "Login created on every node for Ansible."
  type        = string
  default     = "ubuntu"
}

variable "ssh_public_keys" {
  description = "SSH public keys authorised for admin_user on every node."
  type        = list(string)

  validation {
    condition     = length(var.ssh_public_keys) > 0
    error_message = "At least one SSH public key is required; password logins are disabled."
  }
}

variable "dns_domain" {
  description = "DNS domain for node FQDNs."
  type        = string
  default     = "aura.lab"
}

variable "networks" {
  description = "Addressing plan. Keys are referenced by name below, so mgmt, external, tunnel and storage must all exist."
  type = map(object({
    cidr = string
    mode = string
    mtu  = optional(number, 1500)
  }))
  default = {
    mgmt     = { cidr = "10.0.10.0/24", mode = "nat" }
    external = { cidr = "10.0.20.0/24", mode = "route" }
    tunnel   = { cidr = "10.0.30.0/24", mode = "none", mtu = 9000 }
    storage  = { cidr = "10.0.40.0/24", mode = "none", mtu = 9000 }
  }

  validation {
    condition     = length(setsubtract(["mgmt", "external", "tunnel", "storage"], keys(var.networks))) == 0
    error_message = "networks must define mgmt, external, tunnel and storage."
  }
}

variable "internal_vip_host_number" {
  description = "Host number of the Kolla internal API VIP (keepalived) on the mgmt network."
  type        = number
  default     = 250
}

variable "controllers" {
  description = "Controller sizing. Runs the API services, Galera, RabbitMQ, OVN central and the Neutron network role."
  type = object({
    count            = optional(number, 3)
    vcpu             = optional(number, 4)
    memory_mib       = optional(number, 8192)
    os_disk_size_gib = optional(number, 100)
  })
  default = {}

  validation {
    condition     = var.controllers.count % 2 == 1
    error_message = "Use an odd number of controllers so Galera and RabbitMQ can keep quorum."
  }
}

variable "computes" {
  description = "Compute (hypervisor) sizing. Nested virtualisation is enabled so these can run tenant VMs."
  type = object({
    count            = optional(number, 2)
    vcpu             = optional(number, 8)
    memory_mib       = optional(number, 16384)
    os_disk_size_gib = optional(number, 100)
  })
  default = {}

  validation {
    condition     = var.computes.count >= 1
    error_message = "At least one compute node is required."
  }
}

variable "ceph" {
  description = "Ceph storage node sizing. Each data disk becomes one OSD."
  type = object({
    count               = optional(number, 3)
    vcpu                = optional(number, 2)
    memory_mib          = optional(number, 4096)
    os_disk_size_gib    = optional(number, 50)
    data_disk_sizes_gib = optional(list(number), [50, 50])
  })
  default = {}

  validation {
    condition     = var.ceph.count >= 3
    error_message = "Ceph needs at least 3 nodes for the default replicated pool size of 3."
  }
}
