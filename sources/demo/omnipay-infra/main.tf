terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_db_instance" "ledger_postgres" {
  identifier             = "omnipay-ledger-postgres"
  engine                 = "postgres"
  instance_class         = "db.t4g.micro"
  allocated_storage      = 20
  username               = "omnipay"
  password               = "demo-password-only"
  db_name                = "ledger"
  skip_final_snapshot    = true
  publicly_accessible    = false
  deletion_protection    = false
}

resource "aws_s3_bucket" "raw_events" {
  bucket = "omnipay-raw-events-demo"
}
