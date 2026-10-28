output "controllers" {
  description = "Controller nodes keyed by hostname, with their per-network addresses."
  value       = module.controllers.nodes
}

output "computes" {
  description = "Compute nodes keyed by hostname, with their per-network addresses."
  value       = module.computes.nodes
}

output "ceph" {
  description = "Ceph nodes keyed by hostname, with their per-network addresses."
  value       = module.ceph.nodes
}

output "internal_vip" {
  description = "Keepalived VIP that fronts the OpenStack APIs."
  value       = local.inventory.all.vars.aura_internal_vip
}

output "ansible_inventory_path" {
  description = "Path of the generated Ansible inventory."
  value       = abspath(local_file.ansible_inventory.filename)
}
