# ── GitHub OIDC Provider ──────────────────────────────────────────────────────
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

# Provision it if it doesn't already exist in your account:
# resource "aws_iam_openid_connect_provider" "github" {
#   url             = "https://token.actions.githubusercontent.com"
#   client_id_list  = ["sts.amazonaws.com"]
#   thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
# }

# ── Shared ECR push/pull policy ───────────────────────────────────────────────
data "aws_iam_policy_document" "ecr" {
  statement {
    actions = [
      "ecr:GetAuthorizationToken",
    ]
    resources = ["*"]
  }
  statement {
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:CompleteLayerUpload",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = [var.ecr_repository_arn]
  }
}

resource "aws_iam_policy" "ecr" {
  name   = "${var.project}-ecr-push-pull"
  policy = data.aws_iam_policy_document.ecr.json
}

# ── Integration deploy role ───────────────────────────────────────────────────
data "aws_iam_policy_document" "github_assume_integration" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_org}/${var.github_repo}:ref:refs/heads/add-ci-cd",
                  "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/integration"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "github_actions_integration" {
  name               = "${var.project}-github-actions-integration"
  assume_role_policy = data.aws_iam_policy_document.github_assume_integration.json
}

resource "aws_iam_role_policy_attachment" "integration_ecr" {
  role       = aws_iam_role.github_actions_integration.name
  policy_arn = aws_iam_policy.ecr.arn
}

data "aws_iam_policy_document" "ecs_deploy_integration" {
  statement {
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
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.ecs_task_execution.arn, aws_iam_role.ecs_task.arn]
  }
}

resource "aws_iam_role_policy" "ecs_deploy_integration" {
  name   = "ecs-deploy"
  role   = aws_iam_role.github_actions_integration.id
  policy = data.aws_iam_policy_document.ecs_deploy_integration.json
}

# ── Production deploy role ────────────────────────────────────────────────────
# data "aws_iam_policy_document" "github_assume_production" {
#   statement {
#     actions = ["sts:AssumeRoleWithWebIdentity"]
#     principals {
#       type        = "Federated"
#       identifiers = [data.aws_iam_openid_connect_provider.github.arn]
#     }
#     condition {
#       test     = "StringEquals"
#       variable = "token.actions.githubusercontent.com:sub"
#       values   = ["repo:${var.github_org}/${var.github_repo}:ref:refs/heads/main"]
#     }
#     condition {
#       test     = "StringEquals"
#       variable = "token.actions.githubusercontent.com:aud"
#       values   = ["sts.amazonaws.com"]
#     }
#   }
# }

# resource "aws_iam_role" "github_actions_production" {
#   name               = "${var.project}-github-actions-production"
#   assume_role_policy = data.aws_iam_policy_document.github_assume_production.json
# }

# resource "aws_iam_role_policy_attachment" "production_ecr" {
#   role       = aws_iam_role.github_actions_production.name
#   policy_arn = aws_iam_policy.ecr.arn
# }

# resource "aws_iam_role_policy" "ecs_deploy_production" {
#   name   = "ecs-deploy"
#   role   = aws_iam_role.github_actions_production.id
#   policy = data.aws_iam_policy_document.ecs_deploy_integration.json
# }

# ── ECS Task Execution Role ───────────────────────────────────────────────────
resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.project}-ecs-task-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_managed" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ── ECS Task Role (runtime permissions) ──────────────────────────────────────
resource "aws_iam_role" "ecs_task" {
  name = "${var.project}-ecs-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}