variable "project"                      {}
variable "environment"                  {}
variable "aws_region"                   {}
variable "aws_account_id"               {}
variable "ecs_task_role_name"           {}
variable "ecs_task_execution_role_name" {}

variable "kms_key_arns" {
  description = "KMS key ARNs used to encrypt secrets. Use ['*'] if not using customer-managed keys."
  type        = list(string)
  default     = ["*"]
}