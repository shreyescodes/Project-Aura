# node-group

Provisions a group of identical KVM guests (controllers, computes, storage nodes)
from a cloud image, with static addressing on every attached network.

## How it works

- **Disks.** Each node gets a copy-on-write OS disk cloned from `base_volume_id`,
  plus one blank qcow2 volume for each entry in `data_disk_sizes_gib`.
- **Addressing.** Node `i` gets `cidrhost(cidr, address_offset + i)` on every
  interface where `configure_address = true`. Addresses are known at plan time,
  so the module doesn't wait for DHCP leases.
- **Interface naming.** Every NIC gets a deterministic MAC,
  `52:54:00:<mac_group_id>:<nic index>:<node index>`. cloud-init's netplan config
  matches on that MAC and renames the NIC (to `mgmt`, `storage` and so on), so
  Ansible and Kolla can refer to interfaces by role.
- **Access.** cloud-init creates `admin_user` with the given SSH keys and turns off
  password logins.

## Usage

```hcl
module "computes" {
  source = "../../modules/node-group"

  name                = "compute"
  node_count          = 2
  vcpu                = 8
  memory_mib          = 16384
  os_disk_size_gib    = 100
  base_volume_id      = libvirt_volume.base.id
  storage_pool        = "default"
  admin_user          = "ubuntu"
  ssh_public_keys     = [file("~/.ssh/id_ed25519.pub")]
  dns_domain          = "aura.lab"
  nameservers         = ["10.0.10.1"]
  mac_group_id        = 2
  address_offset      = 21

  interfaces = [
    { name = "mgmt", network_id = module.networking.networks.mgmt.id, cidr = "10.0.10.0/24", mtu = 1500, gateway = "10.0.10.1" },
    { name = "external", network_id = module.networking.networks.external.id, cidr = "10.0.20.0/24", mtu = 1500, configure_address = false },
  ]
}
```

## Outputs

| Name    | Description                                                                          |
|---------|--------------------------------------------------------------------------------------|
| `nodes` | Map of hostname to `{ domain_id, addresses }`, where `addresses` maps NIC name to IP. |

## Constraints

- A group can have at most 9 nodes, because each group owns a block of 10 host
  numbers in every subnet. Pick an `address_offset` for each group that doesn't
  overlap another group's block.
- `mac_group_id` must be unique per group within an environment.
