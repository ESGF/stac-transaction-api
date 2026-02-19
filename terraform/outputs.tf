output "ecr_repository_url"           { value = module.ecr.repository_url }
output "github_actions_role_arn"      { value = module.iam.github_actions_role_arn }
# output "github_actions_prod_role_arn" { value = module.iam.github_actions_prod_role_arn }
output "integration_alb_dns"          { value = module.ecs_integration.alb_dns_name }
# output "production_alb_dns"           { value = module.ecs_production.alb_dns_name }