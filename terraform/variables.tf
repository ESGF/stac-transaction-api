variable "aws_region"   { default = "us-east-1" }
variable "project"      { default = "stac-transaction-api" }
variable "vpc_id"       {
                            description = "ID of the existing VPC"
                            type        = string
                        }

variable "github_org"   { description = "GitHub org or user owning the repo" }
variable "github_repo"  { description = "GitHub repository name" }

variable "ecr_image_retention_count" { default = 30 }

variable "container_port"   { default = 8000 }
variable "container_cpu"    { default = 512 }
variable "container_memory" { default = 1024 }

variable "integration_desired_count" { default = 1 }
# variable "production_desired_count"  { default = 2 }