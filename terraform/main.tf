terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

data "aws_vpc" "selected" {
  id = var.vpc_id
  tags = { Name = "esgf" }
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.selected.id]
  }
  tags = {
    Tier = "private_nat"  # adjust to match your existing subnet tags
  }
}

data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.selected.id]
  }
  tags = {
    Tier = "public"  # adjust to match your existing subnet tags
  }
}

module "ecr" {
  source                = "./modules/ecr"
  repository_name       = var.project
  image_retention_count = var.ecr_image_retention_count
}

module "iam" {
  source                  = "./modules/iam"
  project                 = var.project
  aws_account_id          = data.aws_caller_identity.current.account_id
  github_org              = var.github_org
  github_repo             = var.github_repo
  ecr_repository_arn      = module.ecr.repository_arn
  integration_cluster_arn = module.ecs_integration.cluster_arn
  integration_service_arn = module.ecs_integration.service_arn
  # production_cluster_arn  = module.ecs_production.cluster_arn
  # production_service_arn  = module.ecs_production.service_arn
}

module "ecs_integration" {
  source                  = "./modules/ecs"
  project                 = var.project
  environment             = "integration"
  vpc_id                  = data.aws_vpc.selected.id
  private_subnet_ids      = data.aws_subnets.private.ids
  public_subnet_ids       = data.aws_subnets.public.ids
  container_port          = var.container_port
  container_cpu           = var.container_cpu
  container_memory        = var.container_memory
  desired_count           = var.integration_desired_count
  ecr_repository_url      = module.ecr.repository_url
  task_execution_role_arn = module.iam.ecs_task_execution_role_arn
  task_role_arn           = module.iam.ecs_task_role_arn
  aws_region              = var.aws_region
}

# module "ecs_production" {
#   source                  = "./modules/ecs"
#   project                 = var.project
#   environment             = "production"
#   vpc_id                  = data.aws_vpc.selected.id
#   private_subnet_ids      = data.aws_subnets.private.ids
#   public_subnet_ids       = data.aws_subnets.public.ids
#   container_port          = var.container_port
#   container_cpu           = var.container_cpu
#   container_memory        = var.container_memory
#   desired_count           = var.production_desired_count
#   ecr_repository_url      = module.ecr.repository_url
#   task_execution_role_arn = module.iam.ecs_task_execution_role_arn
#   task_role_arn           = module.iam.ecs_task_role_arn
#   aws_region              = var.aws_region
# }