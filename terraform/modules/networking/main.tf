terraform {
  required_providers {
    libvirt = {
      source  = "dmacvicar/libvirt"
      version = "~> 0.7.1"
    }
  }
}

# Management Network (VLAN 10, MTU 1500)
resource "libvirt_network" "management" {
  name      = "management-vlan10"
  mode      = "nat"
  domain    = "openstack.local"
  addresses = ["10.0.10.0/24"]
  mtu       = 1500
  autostart = true
}

# External/API Network (VLAN 20, MTU 1500)
resource "libvirt_network" "external" {
  name      = "external-vlan20"
  mode      = "route"
  addresses = ["10.0.20.0/24"]
  mtu       = 1500
  autostart = true
}

# Tunnel Network (VLAN 30, MTU 9000)
resource "libvirt_network" "tunnel" {
  name      = "tunnel-vlan30"
  mode      = "route"
  addresses = ["10.0.30.0/24"]
  mtu       = 9000
  autostart = true
}

# Storage Network (VLAN 40, MTU 9000)
resource "libvirt_network" "storage" {
  name      = "storage-vlan40"
  mode      = "route"
  addresses = ["10.0.40.0/24"]
  mtu       = 9000
  autostart = true
}

output "management_network_id" {
  value = libvirt_network.management.id
}

output "external_network_id" {
  value = libvirt_network.external.id
}

output "tunnel_network_id" {
  value = libvirt_network.tunnel.id
}

output "storage_network_id" {
  value = libvirt_network.storage.id
}
