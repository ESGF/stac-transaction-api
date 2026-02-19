variable "project"                  {}
variable "environment"              {}
variable "vpc_id"                   {}
variable "private_subnet_ids"       { type = list(string) }
variable "public_subnet_ids"        { type = list(string) }
variable "container_port"           { default = 8000 }
variable "container_cpu"            { default = 512 }
variable "container_memory"         { default = 1024 }
variable "desired_count"            { default = 1 }
variable "ecr_repository_url"       {}
variable "task_execution_role_arn"  {}
variable "task_role_arn"            {}
variable "aws_region"               {}