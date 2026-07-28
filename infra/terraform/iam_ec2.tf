# ── Role the EC2 instance itself runs as ──
data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2_instance" {
  name               = "${var.project_name}-ec2-instance"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

# Lets AWS Systems Manager (Run Command / Session Manager) reach the
# instance without opening SSH (port 22) to the internet.
resource "aws_iam_role_policy_attachment" "ec2_ssm" {
  role       = aws_iam_role.ec2_instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "ec2_instance_permissions" {
  # Pull the image at deploy time.
  statement {
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
    ]
    resources = [aws_ecr_repository.backend.arn]
  }

  # Read the env vars at deploy time.
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.backend.arn]
  }
}

resource "aws_iam_role_policy" "ec2_instance_permissions" {
  name   = "backend-runtime"
  role   = aws_iam_role.ec2_instance.id
  policy = data.aws_iam_policy_document.ec2_instance_permissions.json
}

resource "aws_iam_instance_profile" "ec2_instance" {
  name = "${var.project_name}-ec2-instance"
  role = aws_iam_role.ec2_instance.name
}
