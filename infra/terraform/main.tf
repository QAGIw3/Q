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