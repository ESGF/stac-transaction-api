variable "project"                 {}
variable "service_name"            {}
variable "environment"             {}
variable "cluster_id"              {}
variable "vpc_id"                  {}
variable "private_subnet_ids"      { type = list(string) }
variable "public_subnet_ids"       { type = list(string) }
variable "ecr_repository_url"      {}
variable "task_execution_role_arn" {}
variable "task_role_arn"           {}
variable "aws_region"              {}
variable "container_port"          { default = 8080 }
variable "container_cpu"           { default = 512 }
variable "container_memory"        { default = 1024 }
variable "desired_count"           { default = 1 }
variable "health_check_path"       { default = "/health" }
variable "log_retention_days"      { default = 30 }