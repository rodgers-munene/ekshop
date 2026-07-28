variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Short name used to prefix/tag all resources"
  type        = string
  default     = "ekshop"
}

variable "github_repository" {
  description = "GitHub repo allowed to assume the deploy role, as owner/repo"
  type        = string
  default     = "rodgers-munene/ekshop"
}

variable "github_branch" {
  description = "Branch allowed to assume the deploy role and trigger deploys"
  type        = string
  default     = "main"
}

variable "ec2_instance_type" {
  description = "EC2 instance type for the backend (t3.micro is free-tier eligible on new accounts)"
  type        = string
  default     = "t3.micro"
}

variable "plain_env" {
  description = "Non-sensitive backend environment variables (see terraform.tfvars.example)"
  type        = map(string)
  default     = {}
}

variable "secret_env" {
  description = "Sensitive backend environment variables, stored in Secrets Manager (see terraform.tfvars.example)"
  type        = map(string)
  sensitive   = true
  default     = {}
}
