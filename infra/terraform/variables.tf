variable "kubeconfig_path" {
  description = "Path to the kubeconfig file used by Terraform to access the Kubernetes cluster."
  type        = string
  default     = "~/.kube/config"
}

variable "namespace" {
  description = "Kubernetes namespace where all platform services will be deployed."
  type        = string
  default     = "q-platform"
}

variable "pulsar_chart_version" {
  description = "Helm chart version for Apache Pulsar."
  type        = string
  default     = "5.1.4"
}

variable "cassandra_chart_version" {
  description = "Helm chart version for Cassandra (Bitnami)."
  type        = string
  default     = "12.6.3"
}

variable "elasticsearch_chart_version" {
  description = "Helm chart version for Elasticsearch."
  type        = string
  default     = "8.9.2"
}

variable "janusgraph_chart_version" {
  description = "Helm chart version for JanusGraph."
  type        = string
  default     = "0.6.1"
}

variable "ignite_chart_version" {
  description = "Helm chart version for Apache Ignite."
  type        = string
  default     = "1.1.0"
}

variable "flink_chart_version" {
  description = "Helm chart version for Apache Flink (Bitnami)."
  type        = string
  default     = "0.5.0"
}

variable "minio_chart_version" {
  description = "Helm chart version for MinIO."
  type        = string
  default     = "5.0.10"
}

variable "argocd_chart_version" {
  description = "Helm chart version for ArgoCD."
  type        = string
  default     = "5.51.1"
}

variable "harbor_chart_version" {
  description = "Helm chart version for Harbor."
  type        = string
  default     = "1.13.2"
}

variable "tempo_chart_version" {
  description = "Helm chart version for Grafana Tempo."
  type        = string
  default     = "1.8.0"
}

variable "istio_base_chart_version" {
  description = "Helm chart version for Istio Base."
  type        = string
  default     = "1.21.0"
}

variable "istiod_chart_version" {
  description = "Helm chart version for IstioD (Control Plane)."
  type        = string
  default     = "1.21.0"
}

variable "istio_gateway_chart_version" {
  description = "Helm chart version for Istio Ingress Gateway."
  type        = string
  default     = "1.21.0"
}

variable "seatunnel_chart_version" {
  description = "The version of the Apache SeaTunnel Helm chart to deploy."
  type        = string
  default     = "2.3.10"
}

variable "keycloak_issuer_url" {
  type        = string
  description = "The OIDC issuer URL for the Keycloak realm."
  default     = "http://localhost:8080/realms/q-platform" # Example default for local dev
} 