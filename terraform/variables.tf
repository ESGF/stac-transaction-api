variable "aws_region" {
  description = "AWS region to deploy resources into"
  default     = "us-east-1"
}

variable "project" {
  description = "Top-level project name, used for cluster naming and tagging"
  type        = string
}

variable "vpc_id" {
  description = "ID of the existing VPC"
  type        = string
}

variable "ecr_image_retention_count" {
  description = "Number of images to retain in each ECR repository"
  default     = 30
}

variable "services" {
  description = "Map of services to deploy into the cluster"
  type = map(object({
    container_port     = number
    container_cpu      = number
    container_memory   = number
    health_check_path  = string
    log_retention_days = number
    desired_count      = number
    github_org         = string
    github_repo        = string
  }))
}