locals {
  secretsmanager_arn = "arn:aws:secretsmanager:${var.aws_region}:${var.aws_account_id}:secret:${var.project}/${var.environment}/*"
  ssm_arn            = "arn:aws:ssm:${var.aws_region}:${var.aws_account_id}:parameter/${var.project}/${var.environment}/*"
}

data "aws_iam_policy_document" "secrets" {
  statement {
    sid    = "SecretsManagerAccess"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = [local.secretsmanager_arn]
  }

  statement {
    sid    = "KMSDecrypt"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey",
    ]
    resources = var.kms_key_arns
  }
}

resource "aws_iam_policy" "secrets" {
  name        = "${var.project}-${var.environment}-secrets-access"
  description = "Allows read access to Secrets Manager for ${var.project} ${var.environment}"
  policy      = data.aws_iam_policy_document.secrets.json

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

# Runtime access — app code calling Secrets Manager directly
resource "aws_iam_role_policy_attachment" "ecs_task_role_secrets" {
  role       = var.ecs_task_role_name
  policy_arn = aws_iam_policy.secrets.arn
}

# Startup access — ECS agent fetching secrets to inject as env vars
resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_secrets" {
  role       = var.ecs_task_execution_role_name
  policy_arn = aws_iam_policy.secrets.arn
}