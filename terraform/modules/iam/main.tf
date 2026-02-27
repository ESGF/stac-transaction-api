# ─────────────────────────────────────────────
# GitHub OIDC Provider
# ─────────────────────────────────────────────
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

# resource "aws_iam_openid_connect_provider" "github" {
#   url             = "https://token.actions.githubusercontent.com"
#   client_id_list  = ["sts.amazonaws.com"]
#   thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
# }

# ─────────────────────────────────────────────
# Shared ECR push/pull policy
# ─────────────────────────────────────────────
data "aws_iam_policy_document" "ecr" {
  statement {
    sid       = "ECRAuthToken"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "ECRRepositoryAccess"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:CompleteLayerUpload",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = var.ecr_repository_arns
  }
}

resource "aws_iam_policy" "ecr" {
  name        = "${var.project}-ecr-push-pull"
  description = "Allows push and pull to all ${var.project} ECR repositories"
  policy      = data.aws_iam_policy_document.ecr.json
}

# ─────────────────────────────────────────────
# Shared ECS deploy policy
# ─────────────────────────────────────────────
data "aws_iam_policy_document" "ecs_deploy" {
  statement {
    sid = "ECSDeployAccess"
    actions = [
      "ecs:RegisterTaskDefinition",
      "ecs:DescribeTaskDefinition",
      "ecs:DescribeServices",
      "ecs:UpdateService",
      "ecs:ListTaskDefinitions",
    ]
    resources = ["*"]
  }

  statement {
    sid     = "PassECSRoles"
    actions = ["iam:PassRole"]
    resources = [
      aws_iam_role.ecs_task_execution.arn,
      aws_iam_role.ecs_task.arn,
    ]
  }
}

# ─────────────────────────────────────────────
# ECS Task Execution Role
# Used by ECS agent at container startup to:
#   - pull image from ECR
#   - fetch and inject secrets
#   - write logs to CloudWatch
# ─────────────────────────────────────────────
resource "aws_iam_role" "ecs_task_execution" {
  name        = "${var.project}-ecs-task-execution"
  description = "Assumed by the ECS agent at task startup to pull images and inject secrets"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task_execution_logs" {
  name = "cloudwatch-log-group-create"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogGroup"]
      Resource = "arn:aws:logs:*:${var.aws_account_id}:log-group:/ecs/${var.project}/*"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_managed" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ─────────────────────────────────────────────
# ECS Task Role
# Used by the running container at runtime for
# any direct AWS SDK calls from app code
# ─────────────────────────────────────────────
resource "aws_iam_role" "ecs_task" {
  name        = "${var.project}-ecs-task"
  description = "Assumed by the running container for runtime AWS access"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# ─────────────────────────────────────────────
# GitHub Actions — Integration Role
# Trust policy is built dynamically from each
# service's github_org and github_repo values,
# allowing multiple repos to assume this role.
#
# Trusted branches: integration, add-ci-cd
# ─────────────────────────────────────────────
locals {
  # Build the list of allowed sub claims for integration
  # One entry per branch per service repo
  integration_sub_claims = flatten([
    for svc in values(var.services) : [
      "repo:${svc.github_org}/${svc.github_repo}:ref:refs/heads/integration",
      "repo:${svc.github_org}/${svc.github_repo}:ref:refs/heads/add-ci-cd",
    ]
  ])

  # Build the list of allowed sub claims for production
  # production_sub_claims = [
  #   for svc in values(var.services) :
  #   "repo:${svc.github_org}/${svc.github_repo}:ref:refs/heads/main"
  # ]
}

data "aws_iam_policy_document" "github_assume_integration" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = local.integration_sub_claims
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "github_actions_integration" {
  name        = "${var.project}-github-actions-integration"
  description = "Assumed by GitHub Actions on integration and add-ci-cd branches"

  assume_role_policy = data.aws_iam_policy_document.github_assume_integration.json
}

resource "aws_iam_role_policy_attachment" "github_integration_ecr" {
  role       = aws_iam_role.github_actions_integration.name
  policy_arn = aws_iam_policy.ecr.arn
}

resource "aws_iam_role_policy" "github_integration_ecs_deploy" {
  name   = "ecs-deploy"
  role   = aws_iam_role.github_actions_integration.id
  policy = data.aws_iam_policy_document.ecs_deploy.json
}

# ─────────────────────────────────────────────
# GitHub Actions — Production Role
# Trusted branch: main (exact match only)
#
# Uncomment when enabling production.
# ─────────────────────────────────────────────

# data "aws_iam_policy_document" "github_assume_production" {
#   statement {
#     actions = ["sts:AssumeRoleWithWebIdentity"]
#
#     principals {
#       type        = "Federated"
#       identifiers = [data.aws_iam_openid_connect_provider.github.arn]
#     }
#
#     condition {
#       test     = "StringEquals"
#       variable = "token.actions.githubusercontent.com:sub"
#       values   = local.production_sub_claims
#     }
#
#     condition {
#       test     = "StringEquals"
#       variable = "token.actions.githubusercontent.com:aud"
#       values   = ["sts.amazonaws.com"]
#     }
#   }
# }

# resource "aws_iam_role" "github_actions_production" {
#   name        = "${var.project}-github-actions-production"
#   description = "Assumed by GitHub Actions on main branch only"
#
#   assume_role_policy = data.aws_iam_policy_document.github_assume_production.json
# }

# resource "aws_iam_role_policy_attachment" "github_production_ecr" {
#   role       = aws_iam_role.github_actions_production.name
#   policy_arn = aws_iam_policy.ecr.arn
# }

# resource "aws_iam_role_policy" "github_production_ecs_deploy" {
#   name   = "ecs-deploy"
#   role   = aws_iam_role.github_actions_production.id
#   policy = data.aws_iam_policy_document.ecs_deploy.json
# }