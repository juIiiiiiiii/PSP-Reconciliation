# PSP Reconciliation Platform - Terraform Infrastructure
# AWS Multi-AZ, Multi-Region Deployment

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    bucket = "psp-reconciliation-terraform-state"
    key    = "terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "PSP-Reconciliation"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# VPC and Networking
module "vpc" {
  source = "./modules/vpc"
  
  vpc_cidr             = var.vpc_cidr
  availability_zones   = var.availability_zones
  environment          = var.environment
}

# RDS PostgreSQL
module "rds" {
  source = "./modules/rds"
  
  vpc_id               = module.vpc.vpc_id
  subnet_ids           = module.vpc.private_data_subnet_ids
  db_instance_class    = var.db_instance_class
  db_name              = var.db_name
  db_username          = var.db_username
  environment          = var.environment
  
  depends_on = [module.vpc]
}

# ElastiCache Redis
module "redis" {
  source = "./modules/redis"
  
  vpc_id              = module.vpc.vpc_id
  subnet_ids          = module.vpc.private_data_subnet_ids
  node_type           = var.redis_node_type
  environment         = var.environment
  
  depends_on = [module.vpc]
}

# Kinesis Data Streams
module "kinesis" {
  source = "./modules/kinesis"
  
  stream_name         = "psp-reconciliation-events"
  shard_count         = var.kinesis_shard_count
  retention_hours     = 24
  environment         = var.environment
}

# S3 Buckets
module "s3" {
  source = "./modules/s3"
  
  bucket_prefix       = "psp-reconciliation"
  environment         = var.environment
  enable_versioning  = true
  enable_lifecycle   = true
}

# ECS Fargate
module "ecs" {
  source = "./modules/ecs"
  
  vpc_id              = module.vpc.vpc_id
  subnet_ids          = module.vpc.private_app_subnet_ids
  environment         = var.environment
  db_endpoint         = module.rds.endpoint
  redis_endpoint      = module.redis.endpoint
  kinesis_stream_name = module.kinesis.stream_name
  
  depends_on = [module.vpc, module.rds, module.redis, module.kinesis]
}

# Application Load Balancer
module "alb" {
  source = "./modules/alb"
  
  vpc_id              = module.vpc.vpc_id
  subnet_ids          = module.vpc.public_subnet_ids
  environment         = var.environment
  
  depends_on = [module.vpc]
}

# DynamoDB (Idempotency)
module "dynamodb" {
  source = "./modules/dynamodb"
  
  table_name          = "idempotency_keys"
  environment         = var.environment
}

# CloudWatch
module "cloudwatch" {
  source = "./modules/cloudwatch"
  
  environment = var.environment
}

# Secrets Manager
module "secrets" {
  source = "./modules/secrets"
  
  environment = var.environment
}


