output "ecr_repository_urls" {
  value = { for k, v in module.ecr : k => v.repository_url }
}

output "integration_service_urls" {
  value = { for k, v in module.services_integration : k => v.alb_dns_name }
}

# output "production_service_urls" {
#   value = { for k, v in module.services_production : k => v.alb_dns_name }
# }

output "github_actions_integration_role_arn" {
  value = module.iam.github_actions_integration_role_arn
}

# output "github_actions_production_role_arn" {
#   value = module.iam.github_actions_production_role_arn
# }

output "cluster_integration_name" {
  value = module.cluster_integration.cluster_name
}

# output "cluster_production_name" {
#   value = module.cluster_production.cluster_name
# }