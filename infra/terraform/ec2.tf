# Uses the account's default VPC/subnet rather than standing up custom
# networking — keeps this to a single plain instance, no ALB/NAT to manage.
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  # Standard AL2023 only (not "al2023-ami-minimal-*", which excludes
  # amazon-ssm-agent — SSM Run Command is how we deploy, so it must be
  # preinstalled on first boot).
  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_security_group" "backend" {
  name        = "${var.project_name}-backend"
  description = "Backend EC2 instance - HTTP(S) in, no SSH (use SSM Session Manager)"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS (for once a domain + TLS is set up)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "backend" {
  ami                         = data.aws_ami.al2023.id
  instance_type               = var.ec2_instance_type
  subnet_id                   = data.aws_subnets.default.ids[0]
  vpc_security_group_ids      = [aws_security_group.backend.id]
  iam_instance_profile        = aws_iam_instance_profile.ec2_instance.name
  associate_public_ip_address = true

  # Docker + the SSM agent (already preinstalled on AL2023) is all this
  # instance needs; the actual app container is pulled and started by the
  # CI deploy step over SSM, not at boot.
  user_data = <<-EOF
    #!/bin/bash
    dnf install -y docker
    systemctl enable --now docker
  EOF

  tags = {
    Name = "${var.project_name}-backend"
  }
}

# Keeps a stable public IP across instance stop/start/replace.
resource "aws_eip" "backend" {
  instance = aws_instance.backend.id
  domain   = "vpc"
}
