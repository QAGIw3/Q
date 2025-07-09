# Q Platform - Infrastructure as Code (IaC)

This directory contains the Terraform configuration for deploying the entire Q Platform's core infrastructure services to a Kubernetes cluster.

## Deployed Services

This Terraform setup will deploy and configure the following services into the `q-platform` namespace:

-   **Keycloak**: For identity and access management.
-   **Milvus**: As our core vector database.
-   **Harbor**: A private container registry for our service images.
-   **Prometheus**: For collecting and querying time-series metrics.
-   **Grafana**: For visualizing metrics and building dashboards.
-   **ArgoCD**: For continuous, GitOps-based application deployment.
-   **Istio Policies**: The necessary `RequestAuthentication` and `AuthorizationPolicy` resources to secure the service mesh.
-   (Other core data services like Pulsar can also be managed here).

## Prerequisites

1.  **Terraform**: Install Terraform (version >= 1.4.0).
2.  **kubectl**: Install `kubectl` and ensure it is configured to point to your target Kubernetes cluster.
3.  **Helm**: Install the Helm CLI.

## Deployment Steps

### Step 1: Initialize Terraform

Navigate to this directory and initialize Terraform. This will download the necessary providers (Kubernetes, Helm).

```bash
cd infra/terraform
terraform init
```

### Step 2: Review and Customize Configuration (Optional)

1.  **Service Versions**: The versions for all Helm charts are pinned in `main.tf` for stability.
2.  **Service Values**: Default configurations for all services are in the `values/` directory. You can modify these files to change service settings (e.g., resource limits, persistence sizes).
3.  **Keycloak URL**: The Istio security policy depends on the Keycloak issuer URL. The default is `http://localhost:8080/realms/q-platform`. If your Keycloak will be exposed at a different address, you can override this variable.

    Create a `terraform.tfvars` file:
    ```tf
    keycloak_issuer_url = "https://your-keycloak-domain.com/realms/q-platform"
    ```

### Step 3: Apply the Terraform Plan

Apply the configuration to deploy all the services to your cluster.

```bash
terraform apply -auto-approve
```

This command will:
-   Create the `q-platform` namespace if it doesn't exist.
-   Add the required Helm repositories (`bitnami`, `milvus`, `goharbor`, `prometheus-community`, `grafana`, `argo`).
-   Deploy Keycloak, Milvus, Harbor, Prometheus, Grafana, and ArgoCD using their respective configurations in the `values/` directory.
-   Apply the Istio security policies to your cluster.

## Post-Deployment

After the `apply` command finishes, you can use `kubectl get pods --all-namespaces` to see the services starting up. You will also need to find the external IP addresses of the `LoadBalancer` services for Keycloak, Milvus, Harbor, Grafana, and the ArgoCD Server to access their UIs and APIs.

```bash
kubectl get svc --all-namespaces
```

## Destroying the Infrastructure

To tear down all the deployed services, run the destroy command:

```bash
terraform destroy -auto-approve
``` 