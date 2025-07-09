terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.0.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = ">= 2.0.0"
    }
  }
}

provider "kubernetes" {
  alias = "primary"
  # Configuration for the primary region's cluster
}

provider "kubernetes" {
  alias = "secondary"
  # Configuration for the secondary region's cluster
}

provider "helm" {
  kubernetes {
    # Assumes kubectl is configured
  }
}

# --- Helm Chart Repositories ---

resource "helm_repository" "bitnami" {
  name = "bitnami"
  url  = "https://charts.bitnami.com/bitnami"
}

resource "helm_repository" "milvus" {
  name = "milvus"
  url  = "https://milvus-io.github.io/milvus-helm/"
}

resource "helm_repository" "goharbor" {
  name = "goharbor"
  url  = "https://helm.goharbor.io"
}

resource "helm_repository" "prometheus_community" {
  name = "prometheus-community"
  url  = "https://prometheus-community.github.io/helm-charts"
}

resource "helm_repository" "grafana" {
  name = "grafana"
  url  = "https://grafana.github.io/helm-charts"
}

resource "helm_repository" "argo" {
  name = "argo"
  url  = "https://argoproj.github.io/argo-helm"
}

resource "helm_repository" "hashicorp" {
  name = "hashicorp"
  url  = "https://helm.releases.hashicorp.com"
}

# --- Helm Releases for Core Infrastructure ---

resource "helm_release" "keycloak_primary" {
  provider   = kubernetes.primary
  name       = "keycloak"
  repository = helm_repository.bitnami.name
  chart      = "keycloak"
  version    = "18.2.1" # Pinning version for stability
  namespace  = "q-platform"
  create_namespace = true

  values = [
    file("${path.module}/values/keycloak.yaml")
  ]
}

resource "helm_release" "keycloak_secondary" {
  provider   = kubernetes.secondary
  name       = "keycloak"
  repository = helm_repository.bitnami.name
  chart      = "keycloak"
  version    = "18.2.1" # Pinning version for stability
  namespace  = "q-platform"
  create_namespace = true

  values = [
    file("${path.module}/values/keycloak.yaml")
  ]
}

resource "helm_release" "milvus" {
  name       = "milvus"
  repository = helm_repository.milvus.name
  chart      = "milvus"
  version    = "4.0.12" # Pinning version for stability
  namespace  = "q-platform"

  values = [
    file("${path.module}/values/milvus.yaml")
  ]
}

resource "helm_release" "harbor" {
  name       = "harbor"
  repository = helm_repository.goharbor.name
  chart      = "harbor"
  version    = "1.13.2" # Pinning version for stability
  namespace  = "q-platform"

  values = [
    file("${path.module}/values/harbor.yaml")
  ]
}

# --- Helm Releases for Observability ---

resource "helm_release" "prometheus" {
  name       = "prometheus"
  repository = helm_repository.prometheus_community.name
  chart      = "prometheus"
  version    = "25.4.0" # Pinning version for stability
  namespace  = "q-platform"

  values = [
    file("${path.module}/values/prometheus.yaml")
  ]
}

resource "helm_release" "grafana" {
  name       = "grafana"
  repository = helm_repository.grafana.name
  chart      = "grafana"
  version    = "7.3.5" # Pinning version for stability
  namespace  = "q-platform"

  values = [
    file("${path.module}/values/grafana.yaml")
  ]
  depends_on = [helm_release.prometheus]
}

# --- Helm Releases for GitOps ---

resource "helm_release" "argocd" {
  name       = "argo-cd"
  repository = helm_repository.argo.name
  chart      = "argo-cd"
  version    = "5.51.5" # Pinning version for stability
  namespace  = "argocd"
  create_namespace = true

  values = [
    file("${path.module}/values/argocd.yaml")
  ]
}

# --- Helm Releases for Security ---

resource "helm_release" "vault" {
  name       = "vault"
  repository = helm_repository.hashicorp.name
  chart      = "vault"
  version    = "0.27.0" # Pinning version for stability
  namespace  = "vault"
  create_namespace = true

  values = [
    file("${path.module}/values/vault.yaml")
  ]
} 