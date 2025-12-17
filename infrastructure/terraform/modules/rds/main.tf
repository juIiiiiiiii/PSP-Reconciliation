# RDS PostgreSQL Module

resource "aws_db_subnet_group" "main" {
  name       = "${var.environment}-psp-reconciliation-db-subnet-group"
  subnet_ids = var.subnet_ids
  
  tags = {
    Name = "${var.environment}-psp-reconciliation-db-subnet-group"
  }
}

resource "aws_db_instance" "main" {
  identifier = "${var.environment}-psp-reconciliation-db"
  
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = var.db_instance_class
  
  db_name  = var.db_name
  username = var.db_username
  password = data.aws_secretsmanager_secret_version.db_password.secret_string
  
  allocated_storage     = 500
  max_allocated_storage = 2000
  storage_type          = "gp3"
  storage_encrypted     = true
  
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids  = [aws_security_group.db.id]
  publicly_accessible     = false
  multi_az                = true
  
  backup_retention_period = 30
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"
  
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  
  performance_insights_enabled = true
  performance_insights_retention_period = 7
  
  skip_final_snapshot = false
  final_snapshot_identifier = "${var.environment}-psp-reconciliation-db-final-snapshot"
  
  tags = {
    Name = "${var.environment}-psp-reconciliation-db"
  }
}

resource "aws_security_group" "db" {
  name        = "${var.environment}-psp-reconciliation-db-sg"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = var.vpc_id
  
  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name = "${var.environment}-psp-reconciliation-db-sg"
  }
}

data "aws_secretsmanager_secret" "db_password" {
  name = "${var.environment}/psp-reconciliation/db-password"
}

data "aws_secretsmanager_secret_version" "db_password" {
  secret_id = data.aws_secretsmanager_secret.db_password.id
}

output "endpoint" {
  value = aws_db_instance.main.endpoint
}

output "address" {
  value = aws_db_instance.main.address
}


