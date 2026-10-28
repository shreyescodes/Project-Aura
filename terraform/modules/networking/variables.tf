variable "name_prefix" {
  description = "Prefix applied to every libvirt network name, so several environments can share one hypervisor."
  type        = string
  default     = "aura"
}

variable "dns_domain" {
  description = "DNS domain served by libvirt's dnsmasq on NAT networks."
  type        = string
}

variable "networks" {
  description = <<-EOT
    Networks to create, keyed by logical name (for example "mgmt" or "storage").
    mode is one of:
      nat   - routed to the outside world through the hypervisor (management/egress).
      route - routed to the hypervisor without NAT (provider network for floating IPs).
      none  - isolated L2 segment with no route off the host (tunnel and storage traffic).
  EOT
  type = map(object({
    cidr = string
    mode = string
    mtu  = optional(number, 1500)
  }))

  validation {
    condition     = alltrue([for n in values(var.networks) : contains(["nat", "route", "none"], n.mode)])
    error_message = "Each network mode must be one of: nat, route, none."
  }

  validation {
    condition     = alltrue([for n in values(var.networks) : can(cidrhost(n.cidr, 1))])
    error_message = "Each network cidr must be a valid IPv4 CIDR block."
  }

  validation {
    condition     = alltrue([for n in values(var.networks) : n.mtu >= 1280 && n.mtu <= 9000])
    error_message = "Each network mtu must be between 1280 and 9000."
  }
}
