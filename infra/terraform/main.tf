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
  # Configuration options for the Kubernetes provider
  # Assumes that kubectl is configured to point to the correct cluster.
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

# --- Helm Releases for Core Infrastructure ---

resource "helm_release" "keycloak" {
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