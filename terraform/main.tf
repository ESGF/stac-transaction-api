terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # backend "s3" {
  #   bucket         = "your-terraform-state-bucket"
  #   key            = "transaction-api/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "terraform-state-lock"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

data "aws_vpc" "this" {
  id = var.vpc_id
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.this.id]
  }
  tags = { Tier = "private_nat" }
}

data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.this.id]
  }
  tags = { Tier = "public" }
}

# ─────────────────────────────────────────────
# ECR — one repo per service
# ─────────────────────────────────────────────
module "ecr" {
  source   = "./modules/ecr"
  for_each = var.services

  repository_name       = each.key
  image_retention_count = var.ecr_image_retention_count
}

# ─────────────────────────────────────────────
# IAM
# ─────────────────────────────────────────────
module "iam" {
  source         = "./modules/iam"
  project        = var.project
  aws_account_id = data.aws_caller_identity.current.account_id

  # Pass the full services map so the IAM module
  # can build per-service OIDC trust policies
  services = var.services

  ecr_repository_arns = [
    for svc in module.ecr : svc.repository_arn
  ]

  integration_cluster_arn = module.cluster_integration.cluster_arn
  integration_service_arns = [
    for svc in module.services_integration : svc.service_arn
  ]

  # production_cluster_arn  = module.cluster_production.cluster_arn
  # production_service_arns = [
  #   for svc in module.services_production : svc.service_arn
  # ]
}

# ─────────────────────────────────────────────
# CLUSTERS — one per environment
# ─────────────────────────────────────────────
module "cluster_integration" {
  source      = "./modules/cluster"
  project     = var.project
  environment = "integration"
}

# module "cluster_production" {
#   source      = "./modules/cluster"
#   project     = var.project
#   environment = "production"
# }

# ─────────────────────────────────────────────
# SECRETS — one per service per environment
# ─────────────────────────────────────────────
module "secrets_integration" {
  source   = "./modules/secrets"
  for_each = var.services

  project                      = each.key
  environment                  = "integration"
  aws_region                   = var.aws_region
  aws_account_id               = data.aws_caller_identity.current.account_id
  ecs_task_role_name           = module.iam.ecs_task_role_name
  ecs_task_execution_role_name = module.iam.ecs_task_execution_role_name
}

# module "secrets_production" {
#   source   = "./modules/secrets"
#   for_each = var.services
#
#   project                      = each.key
#   environment                  = "production"
#   aws_region                   = var.aws_region
#   aws_account_id               = data.aws_caller_identity.current.account_id
#   ecs_task_role_name           = module.iam.ecs_task_role_name
#   ecs_task_execution_role_name = module.iam.ecs_task_execution_role_name
# }

# ─────────────────────────────────────────────
# SERVICES — one per service per environment
# ─────────────────────────────────────────────
module "services_integration" {
  source   = "./modules/service"
  for_each = var.services

  project                 = var.project
  service_name            = each.key
  environment             = "integration"
  cluster_id              = module.cluster_integration.cluster_id
  vpc_id                  = data.aws_vpc.this.id
  private_subnet_ids      = data.aws_subnets.private.ids
  public_subnet_ids       = data.aws_subnets.public.ids
  ecr_repository_url      = module.ecr[each.key].repository_url
  task_execution_role_arn = module.iam.ecs_task_execution_role_arn
  task_role_arn           = module.iam.ecs_task_role_arn
  aws_region              = var.aws_region
  container_port          = each.value.container_port
  container_cpu           = each.value.container_cpu
  container_memory        = each.value.container_memory
  desired_count           = each.value.desired_count
  health_check_path       = each.value.health_check_path
  log_retention_days      = each.value.log_retention_days
}

# module "services_production" {
#   source   = "./modules/service"
#   for_each = var.services
#
#   project                 = var.project
#   service_name            = each.key
#   environment             = "production"
#   cluster_id              = module.cluster_production.cluster_id
#   vpc_id                  = data.aws_vpc.this.id
#   private_subnet_ids      = data.aws_subnets.private.ids
#   public_subnet_ids       = data.aws_subnets.public.ids
#   ecr_repository_url      = module.ecr[each.key].repository_url
#   task_execution_role_arn = module.iam.ecs_task_execution_role_arn
#   task_role_arn           = module.iam.ecs_task_role_arn
#   aws_region              = var.aws_region
#   container_port          = each.value.container_port
#   container_cpu           = each.value.container_cpu
#   container_memory        = each.value.container_memory
#   desired_count           = each.value.desired_count
#   health_check_path       = each.value.health_check_path
#   log_retention_days      = each.value.log_retention_days
# }