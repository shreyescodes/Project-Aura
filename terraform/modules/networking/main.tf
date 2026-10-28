# Each logical network is its own libvirt bridge. In a physical deployment these
# would be VLANs on bonded NICs; see docs/architecture.md for the mapping.
#
# DHCP is disabled everywhere: guests get static addresses through cloud-init
# (see the node-group module), so Ansible inventory is known at plan time and
# never depends on dnsmasq leases.
resource "libvirt_network" "this" {
  for_each = var.networks

  name      = "${var.name_prefix}-${each.key}"
  mode      = each.value.mode
  domain    = each.value.mode == "nat" ? var.dns_domain : null
  addresses = [each.value.cidr]
  mtu       = each.value.mtu
  autostart = true

  dhcp {
    enabled = false
  }

  dns {
    enabled    = each.value.mode == "nat"
    local_only = true
  }
}
