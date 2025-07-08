# Q Platform – Infrastructure Provisioning

This Terraform module deploys the core data & messaging backbone required by the Q Platform to a Kubernetes cluster.

## What Gets Deployed

| Service          | Purpose                              | Helm Chart Source                       |
| ---------------- | ------------------------------------ | --------------------------------------- |
| Apache Pulsar    | Streaming / messaging backbone       | `pulsar.apache.org/charts`              |
| Apache Cassandra | Wide-column store for time-series    | `bitnami/cassandra`                     |
| Elasticsearch    | Full-text & analytics index          | `elastic/elasticsearch`                 |
| JanusGraph       | Property graph DB over Cassandra/ES  | `charts.janusgraph.org`                 |
| Apache Ignite    | In-memory data grid / compute        | `apacheignite/ignite-kubernetes`        |
| Apache Flink     | Stream analytics / batch processing  | `bitnami/flink`                         |
| MinIO            | S3-compatible object storage         | `minio/minio`                           |

All releases are created in a single namespace (default: `q-platform`). Chart versions and resource tuning live in `variables.tf` and the `values/` directory.

## Prerequisites

1. A working Kubernetes cluster (v1.25+ recommended)
2. `kubectl` configured to talk to the cluster (kubeconfig path defaults to `~/.kube/config`)
3. Terraform ≥ 1.4 installed locally
4. Helm ≥ 3.10 installed locally (Terraform Helm provider shells out to Helm)

## Quick Start

```bash
cd infra/terraform
terraform init      # downloads providers and charts
terraform plan      # shows resources to create
terraform apply     # provisions everything
```

Override any variable at apply time, e.g.:

```bash
terraform apply -var namespace=my-q -var pulsar_chart_version=5.2.0
```

## Tearing Down

```bash
terraform destroy
```

## Customizing Helm Values

Each service has a corresponding YAML file under `values/`. Adjust replicas, storage class, resources, etc. as needed.

## Roadmap

- Add Prometheus/Grafana stack (needed for observability)
- Expose Pulsar proxy, Flink UI, and MinIO Console via Ingress
- Add ArgoCD Helm release to bootstrap GitOps
- Parameterize storage classes for on-prem vs. cloud 