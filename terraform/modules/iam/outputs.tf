# ─────────────────────────────────────────────
# ECS roles — consumed by the service and
# secrets modules
# ─────────────────────────────────────────────
output "ecs_task_execution_role_arn" {
  description = "ARN of the ECS task execution role"
  value       = aws_iam_role.ecs_task_execution.arn
}

output "ecs_task_execution_role_name" {
  description = "Name of the ECS task execution role"
  value       = aws_iam_role.ecs_task_execution.name
}

output "ecs_task_role_arn" {
  description = "ARN of the ECS task role"
  value       = aws_iam_role.ecs_task.arn
}

output "ecs_task_role_name" {
  description = "Name of the ECS task role"
  value       = aws_iam_role.ecs_task.name
}

# ─────────────────────────────────────────────
# GitHub Actions roles — add these ARNs as
# secrets in GitHub after running apply
# ─────────────────────────────────────────────
output "github_actions_integration_role_arn" {
  description = "ARN of the GitHub Actions integration role — set as AWS_ROLE_TO_ASSUME in GitHub secrets"
  value       = aws_iam_role.github_actions_integration.arn
}

# ─────────────────────────────────────────────
# Production — uncomment when enabling production
# ─────────────────────────────────────────────

# output "github_actions_production_role_arn" {
#   description = "ARN of the GitHub Actions production role — set as AWS_PROD_ROLE_TO_ASSUME in GitHub secrets"
#   value       = aws_iam_role.github_actions_production.arn
# }