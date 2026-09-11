terraform {
  required_providers {
    libvirt = {
      source  = "dmacvicar/libvirt"
      version = "~> 0.7.1"
    }
  }
}

variable "node_count" {
  description = "Number of controller nodes"
  type        = number
  default     = 3
}

variable "base_image_id" {
  description = "ID of the base OS image (e.g. Ubuntu 22.04 cloud image)"
  type        = string
}

variable "management_network_id" {
  type = string
}

variable "external_network_id" {
  type = string
}

variable "ssh_public_key" {
  description = "SSH public key for root/ubuntu user"
  type        = string
}

# Volume for OS disk
resource "libvirt_volume" "controller_os" {
  count          = var.node_count
  name           = "controller-${count.index}-os.qcow2"
  pool           = "default" # Use default pool, can be parameterized
  base_volume_id = var.base_image_id
  size           = 107374182400 # 100GB in bytes
}

# Cloud-Init for user data (SSH keys, hostname)
resource "libvirt_cloudinit_disk" "controller_init" {
  count     = var.node_count
  name      = "controller-${count.index}-init.iso"
  pool      = "default"
  user_data = <<EOF
#cloud-config
hostname: controller-${count.index}
manage_etc_hosts: true
users:
  - name: ubuntu
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    groups: sudo
    shell: /bin/bash
    ssh-authorized-keys:
      - ${var.ssh_public_key}
EOF
}

resource "libvirt_domain" "controller" {
  count  = var.node_count
  name   = "controller-${count.index}"
  memory = "8192"
  vcpu   = 4

  cloudinit = libvirt_cloudinit_disk.controller_init[count.index].id

  network_interface {
    network_id     = var.management_network_id
    wait_for_lease = true
  }

  network_interface {
    network_id = var.external_network_id
  }

  disk {
    volume_id = libvirt_volume.controller_os[count.index].id
  }

  console {
    type        = "pty"
    target_port = "0"
    target_type = "serial"
  }

  console {
    type        = "pty"
    target_type = "virtio"
    target_port = "1"
  }

  graphics {
    type        = "vnc"
    listen_type = "address"
  }
}

output "controller_ips" {
  value = [for instance in libvirt_domain.controller : instance.network_interface[0].addresses[0]]
}
