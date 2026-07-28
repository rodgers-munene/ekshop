terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Local state by default. For a team setup, switch this to an S3 backend
  # (with a DynamoDB lock table) once one exists.
  # backend "s3" {
  #   bucket = "ekshop-terraform-state"
  #   key    = "backend/terraform.tfstate"
  #   region = "eu-west-1"
  # }
}

provider "aws" {
  region = var.aws_region
}
