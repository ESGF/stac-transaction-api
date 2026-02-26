aws_region = "us-east-1"
project    = "esgf2-cluster"
vpc_id     = "vpc-08bc77acf4f9e08a2"

services = {
  "transaction-api" = {
    container_port     = 8000
    container_cpu      = 512
    container_memory   = 1024
    health_check_path  = "/health"
    log_retention_days = 30
    desired_count      = 1
    github_org         = "ESGF"
    github_repo        = "stac-transaction-api"
  }
}