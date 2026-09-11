terraform {
  required_providers {
    libvirt = {
      source  = "dmacvicar/libvirt"
      version = "~> 0.7.1"
    }
  }
}

provider "libvirt" {
  uri = "qemu:///system"
}

variable "ssh_public_key" {
  description = "SSH public key for all nodes"
  type        = string
}

variable "base_image_id" {
  description = "Absolute path or URI to the base OS image (e.g. /var/lib/libvirt/images/ubuntu-22.04-server-cloudimg-amd64.img)"
  type        = string
  default     = "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
}

module "networking" {
  source = "../../modules/networking"
}

module "openstack_controller" {
  source = "../../modules/openstack-controller"

  node_count            = 3
  base_image_id         = var.base_image_id
  ssh_public_key        = var.ssh_public_key
  management_network_id = module.networking.management_network_id
  external_network_id   = module.networking.external_network_id
}

module "openstack_compute" {
  source = "../../modules/openstack-compute"

  node_count            = 2
  base_image_id         = var.base_image_id
  ssh_public_key        = var.ssh_public_key
  management_network_id = module.networking.management_network_id
  tunnel_network_id     = module.networking.tunnel_network_id
  storage_network_id    = module.networking.storage_network_id
  external_network_id   = module.networking.external_network_id
}

module "ceph_cluster" {
  source = "../../modules/ceph-cluster"

  node_count            = 3
  base_image_id         = var.base_image_id
  ssh_public_key        = var.ssh_public_key
  management_network_id = module.networking.management_network_id
  storage_network_id    = module.networking.storage_network_id
}

output "controller_ips" {
  value = module.openstack_controller.controller_ips
}

output "compute_ips" {
  value = module.openstack_compute.compute_ips
}

output "ceph_ips" {
  value = module.ceph_cluster.ceph_ips
}
