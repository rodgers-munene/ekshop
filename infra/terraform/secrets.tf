resource "aws_secretsmanager_secret" "backend" {
  name        = "${var.project_name}/backend"
  description = "All env vars for the ${var.project_name} backend container, fetched by the deploy script on the EC2 instance"
}

# EC2 has no built-in "plain env var" injection channel like App Runner did,
# so everything (sensitive or not) is sourced from this one secret at
# deploy time.
resource "aws_secretsmanager_secret_version" "backend" {
  secret_id     = aws_secretsmanager_secret.backend.id
  secret_string = jsonencode(merge(var.plain_env, var.secret_env))
}
