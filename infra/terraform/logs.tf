# Container logs otherwise only exist as ephemeral `docker logs` output on
# the instance itself, reachable only via one-off SSM Run Command calls.
# Shipping them to CloudWatch instead gives persistent, searchable,
# `aws logs tail --follow`-able logs with a retention policy.
resource "aws_cloudwatch_log_group" "backend" {
  name              = "/${var.project_name}/backend"
  retention_in_days = 30
}
