variable "project" {
  description = "Top-level project name, used to prefix all IAM role and policy names"
  type        = string
}

variable "aws_account_id" {
  description = "AWS account ID"
  type        = string
}

variable "services" {
  description = "Services map passed from root — used to build per-service OIDC trust policies"
  type = map(object({
    github_org  = string
    github_repo = string

    # The remaining fields are not used by IAM but the
    # type must match the root services variable exactly
    container_port     = number
    container_cpu      = number
    container_memory   = number
    health_check_path  = string
    log_retention_days = number
    desired_count      = number
  }))
}

variable "ecr_repository_arns" {
  description = "List of ECR repository ARNs the GitHub Actions roles are permitted to push and pull"
  type        = list(string)
}

# ─────────────────────────────────────────────
# Integration
# ─────────────────────────────────────────────
variable "integration_cluster_arn" {
  description = "ARN of the integration ECS cluster"
  type        = string
}

variable "integration_service_arns" {
  description = "List of integration ECS service ARNs"
  type        = list(string)
}

# ─────────────────────────────────────────────
# Production — uncomment when enabling production
# ─────────────────────────────────────────────

# variable "production_cluster_arn" {
#   description = "ARN of the production ECS cluster"
#   type        = string
# }

# variable "production_service_arns" {
#   description = "List of production ECS service ARNs"
#   type        = list(string)
# }