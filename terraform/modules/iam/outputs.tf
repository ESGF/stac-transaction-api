output "github_actions_role_arn"      { value = aws_iam_role.github_actions_integration.arn }
# output "github_actions_prod_role_arn" { value = aws_iam_role.github_actions_production.arn }
output "ecs_task_execution_role_arn"  { value = aws_iam_role.ecs_task_execution.arn }
output "ecs_task_role_arn"            { value = aws_iam_role.ecs_task.arn }