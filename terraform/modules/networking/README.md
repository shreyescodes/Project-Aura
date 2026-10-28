# networking

Creates the libvirt networks that model the platform's physical network segments.

Every network has DHCP disabled. Nodes get static addresses from the `node-group`
module, which keeps the Ansible inventory deterministic.

## Usage

```hcl
module "networking" {
  source = "../../modules/networking"

  dns_domain = "aura.lab"
  networks = {
    mgmt    = { cidr = "10.0.10.0/24", mode = "nat" }
    storage = { cidr = "10.0.40.0/24", mode = "none", mtu = 9000 }
  }
}
```

## Inputs

| Name          | Type                                     | Default  | Description                                       |
|---------------|------------------------------------------|----------|---------------------------------------------------|
| `name_prefix` | `string`                                 | `"aura"` | Prefix for libvirt network names.                 |
| `dns_domain`  | `string`                                 | n/a      | Domain served by dnsmasq on `nat` networks.       |
| `networks`    | `map(object({ cidr, mode, mtu }))`       | n/a      | Networks keyed by logical name. `mtu` defaults to 1500. |

`mode` is `nat` (egress through the hypervisor), `route` (routed, no NAT) or `none`
(isolated L2 segment).

## Outputs

| Name       | Description                                                                 |
|------------|-----------------------------------------------------------------------------|
| `networks` | Map of logical name to `{ id, name, cidr, gateway, mtu, mode }`.            |
