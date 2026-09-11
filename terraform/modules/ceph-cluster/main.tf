terraform {
  required_providers {
    libvirt = {
      source  = "dmacvicar/libvirt"
      version = "~> 0.7.1"
    }
  }
}

variable "node_count" {
  description = "Number of Ceph OSD nodes"
  type        = number
  default     = 3
}

variable "base_image_id" {
  description = "ID of the base OS image"
  type        = string
}

variable "management_network_id" {
  type = string
}

variable "storage_network_id" {
  type = string
}

variable "ssh_public_key" {
  type = string
}

# OS Volumes
resource "libvirt_volume" "ceph_os" {
  count          = var.node_count
  name           = "ceph-${count.index}-os.qcow2"
  pool           = "default"
  base_volume_id = var.base_image_id
  size           = 53687091200 # 50GB
}

# Ceph Data Volumes
resource "libvirt_volume" "ceph_data1" {
  count  = var.node_count
  name   = "ceph-${count.index}-data1.qcow2"
  pool   = "default"
  size   = 53687091200 # 50GB
}

resource "libvirt_volume" "ceph_data2" {
  count  = var.node_count
  name   = "ceph-${count.index}-data2.qcow2"
  pool   = "default"
  size   = 53687091200 # 50GB
}

resource "libvirt_cloudinit_disk" "ceph_init" {
  count     = var.node_count
  name      = "ceph-${count.index}-init.iso"
  pool      = "default"
  user_data = <<EOF
#cloud-config
hostname: ceph-${count.index}
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

resource "libvirt_domain" "ceph" {
  count  = var.node_count
  name   = "ceph-${count.index}"
  memory = "4096" # 4GB
  vcpu   = 2

  cloudinit = libvirt_cloudinit_disk.ceph_init[count.index].id

  # Management network
  network_interface {
    network_id     = var.management_network_id
    wait_for_lease = true
  }

  # Storage network (Ceph replication)
  network_interface {
    network_id = var.storage_network_id
  }

  disk {
    volume_id = libvirt_volume.ceph_os[count.index].id
  }

  disk {
    volume_id = libvirt_volume.ceph_data1[count.index].id
  }

  disk {
    volume_id = libvirt_volume.ceph_data2[count.index].id
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

output "ceph_ips" {
  value = [for instance in libvirt_domain.ceph : instance.network_interface[0].addresses[0]]
}
