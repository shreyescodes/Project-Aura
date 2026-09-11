# Mock S3 backend setup for production
# Uncomment and configure with real AWS credentials/bucket for production use.
# terraform {
#   backend "s3" {
#     bucket         = "platform-tfstate"
#     key            = "production/terraform.tfstate"
#     region         = "us-east-1"
#     dynamodb_table = "platform-tfstate-locks"
#     encrypt        = true
#   }
# }

terraform {
  backend "local" {
    path = "terraform.tfstate"
  }
}
