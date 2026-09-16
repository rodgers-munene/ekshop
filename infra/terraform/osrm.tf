resource "aws_security_group" "osrm" {
  name        = "${var.project_name}-osrm"
  description = "OSRM routing service - only backend can reach port 5000"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "OSRM HTTP from backend SG only"
    from_port   = 5000
    to_port     = 5000
    protocol    = "tcp"
    security_groups = [aws_security_group.backend.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-osrm"
  }
}

resource "aws_instance" "osrm" {
  ami                         = var.backend_ami_id
  instance_type               = "t3.small"
  subnet_id                   = data.aws_subnets.default.ids[0]
  vpc_security_group_ids      = [aws_security_group.osrm.id]
  associate_public_ip_address = true

  user_data = <<-EOF
    #!/bin/bash
    dnf install -y docker
    systemctl enable --now docker
    docker run -d --name osrm \
      --restart unless-stopped \
      -p 5000:5000 \
      osrm/osrm-backend:latest \
      osrm-routed --algorithm mld /data/kenya-latest.osrm
  EOF

  tags = {
    Name = "${var.project_name}-osrm"
  }
}

# Stable public IP for the OSRM instance
resource "aws_eip" "osrm" {
  instance = aws_instance.osrm.id
  domain   = "vpc"
}
