terraform {
  required_version = ">= 1.4.0"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.24"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
  }
}

provider "kubernetes" {
  config_path = var.kubeconfig_path
}

provider "helm" {
  kubernetes {
    config_path = var.kubeconfig_path
  }
}

# ----------------------------
# Pulsar
# ----------------------------
resource "helm_release" "pulsar" {
  name       = "pulsar"
  repository = "https://pulsar.apache.org/charts"
  chart      = "pulsar"
  version    = var.pulsar_chart_version

  namespace  = var.namespace
  create_namespace = true

  values = [
    file("${path.module}/values/pulsar.yaml")
  ]
}

# ----------------------------
# Cassandra (bitnami chart)
# ----------------------------
resource "helm_release" "cassandra" {
  name       = "cassandra"
  repository = "https://charts.bitnami.com/bitnami"
  chart      = "cassandra"
  version    = var.cassandra_chart_version

  namespace  = var.namespace
  values = [
    file("${path.module}/values/cassandra.yaml")
  ]
}

# ----------------------------
# Elasticsearch (elastic helm)
# ----------------------------
resource "helm_release" "elasticsearch" {
  name       = "elasticsearch"
  repository = "https://helm.elastic.co"
  chart      = "elasticsearch"
  version    = var.elasticsearch_chart_version

  namespace  = var.namespace
  values = [
    file("${path.module}/values/elasticsearch.yaml")
  ]
}

# ----------------------------
# JanusGraph (uses community chart)
# ----------------------------
resource "helm_release" "janusgraph" {
  name       = "janusgraph"
  repository = "https://charts.janusgraph.org"
  chart      = "janusgraph"
  version    = var.janusgraph_chart_version

  namespace  = var.namespace
  values = [
    file("${path.module}/values/janusgraph.yaml")
  ]

  depends_on = [helm_release.cassandra, helm_release.elasticsearch]
}

# ----------------------------
# Apache Ignite (gridgain community chart)
# ----------------------------
resource "helm_release" "ignite" {
  name       = "ignite"
  repository = "https://apacheignite.github.io/ignite-kubernetes"
  chart      = "ignite"
  version    = var.ignite_chart_version

  namespace  = var.namespace
  values = [
    file("${path.module}/values/ignite.yaml")
  ]
}

# ----------------------------
# Apache Flink (bitnami)
# ----------------------------
resource "helm_release" "flink" {
  name       = "flink"
  repository = "https://charts.bitnami.com/bitnami"
  chart      = "flink"
  version    = var.flink_chart_version

  namespace  = var.namespace
  values = [
    file("${path.module}/values/flink.yaml")
  ]
}

# ----------------------------
# MinIO
# ----------------------------
resource "helm_release" "minio" {
  name       = "minio"
  repository = "https://charts.min.io/"
  chart      = "minio"
  version    = var.minio_chart_version

  namespace  = var.namespace
  values = [
    file("${path.module}/values/minio.yaml")
  ]
}

# ----------------------------
# ArgoCD (argoproj)
# ----------------------------
resource "helm_release" "argocd" {
  name       = "argocd"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"
  version    = var.argocd_chart_version

  namespace  = var.namespace
  values = [
    file("${path.module}/values/argocd.yaml")
  ]
}

# ----------------------------
# Harbor (goharbor)
# ----------------------------
resource "helm_release" "harbor" {
  name       = "harbor"
  repository = "https://helm.goharbor.io"
  chart      = "harbor"
  version    = var.harbor_chart_version

  namespace  = var.namespace
  values = [
    file("${path.module}/values/harbor.yaml")
  ]
}

# ----------------------------
# Grafana Tempo (for tracing)
# ----------------------------
resource "helm_release" "tempo" {
  name       = "tempo"
  repository = "https://grafana.github.io/helm-charts"
  chart      = "tempo"
  version    = var.tempo_chart_version

  namespace  = var.namespace
  values = [
    file("${path.module}/values/tempo.yaml")
  ]
}

# ----------------------------
# Istio Service Mesh
# ----------------------------
resource "helm_release" "istio_base" {
  name       = "istio-base"
  repository = "https://istio-release.storage.googleapis.com/charts"
  chart      = "base"
  version    = var.istio_base_chart_version

  namespace  = "istio-system"
  create_namespace = true
}

resource "helm_release" "istiod" {
  name       = "istiod"
  repository = "https://istio-release.storage.googleapis.com/charts"
  chart      = "istiod"
  version    = var.istiod_chart_version

  namespace  = "istio-system"
  
  values = [
    file("${path.module}/values/istiod.yaml")
  ]

  depends_on = [helm_release.istio_base]
}

resource "helm_release" "istio_gateway" {
  name       = "istio-ingressgateway"
  repository = "https://istio-release.storage.googleapis.com/charts"
  chart      = "gateway"
  version    = var.istio_gateway_chart_version

  namespace  = "istio-system"
  
  depends_on = [helm_release.istiod]
} 

# ----------------------------
# Apache SeaTunnel
# ----------------------------
resource "helm_release" "seatunnel" {
  name       = "seatunnel"
  repository = "oci://registry-1.docker.io/apache"
  chart      = "seatunnel-helm"
  version    = var.seatunnel_chart_version

  namespace  = var.namespace
  values = [
    file("${path.module}/values/seatunnel.yaml")
  ]
} 