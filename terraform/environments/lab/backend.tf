# The lab runs on one hypervisor and is operated from that host, so state stays
# local. An environment shared by a team should use a remote backend with
# locking (for example S3 with a DynamoDB lock table, or HTTP via GitLab).
terraform {
  backend "local" {
    path = "terraform.tfstate"
  }
}
