variable "location" {
  description = "Azure region"
  default     = "italynorth"
}

variable "project_name" {
  description = "Base name used for resource naming"
  default     = "spotifycharts"
}

variable "sql_admin_username" {
  description = "Admin username for Azure SQL"
  type        = string
}

variable "sql_admin_password" {
  description = "Admin password for Azure SQL"
  type        = string
  sensitive   = true
}

variable "dev_ip_address" {
  description = "Your current public IP, for SQL firewall access"
  type        = string
}