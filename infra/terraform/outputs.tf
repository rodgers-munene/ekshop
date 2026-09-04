output "ecr_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "product_images_bucket" {
  description = "Put this in AWS_S3_BUCKET"
  value       = aws_s3_bucket.product_images.id
}

output "product_images_public_url" {
  description = "Put this in AWS_S3_PUBLIC_URL"
  value       = "https://${aws_s3_bucket.product_images.bucket_regional_domain_name}"
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

output "latest_al2023_ami" {
  description = "Latest AL2023 AMI available. backend_ami_id is pinned and won't track this automatically — copy this value into terraform.tfvars and re-apply only when you deliberately want to upgrade the instance's base image."
  value       = data.aws_ami.al2023.id
}
