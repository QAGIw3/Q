variable "service_name" {
  description = "The name of the service for which to create a Vault role."
  type        = "string"
}

variable "namespace" {
  description = "The Kubernetes namespace the service runs in."
  type        = "string"
}

variable "secrets_path" {
  description = "The path in Vault where the service can read secrets."
  type        = "string"
  default     = "secret/data/*"
} 