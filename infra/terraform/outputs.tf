output "ecr_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "backend_url" {
  description = "Public HTTPS URL of the backend, via sslip.io (no domain purchased — see README)"
  value       = "https://${replace(aws_eip.backend.public_ip, ".", "-")}.sslip.io"
}

output "ec2_instance_id" {
  description = "Put this in the GitHub repo secret EC2_INSTANCE_ID"
  value       = aws_instance.backend.id
}

output "github_actions_role_arn" {
  description = "Put this in the GitHub repo secret AWS_DEPLOY_ROLE_ARN"
  value       = aws_iam_role.github_actions_deploy.arn
}

output "secrets_manager_secret_arn" {
  description = "Put this in the GitHub repo secret SECRETS_MANAGER_ARN"
  value       = aws_secretsmanager_secret.backend.arn
}
