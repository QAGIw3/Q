# Continuous Integration & Deployment (CI/CD)

This document outlines the CI/CD strategy for the Q Platform, which is built on GitHub Actions.

## Reusable Workflow

A reusable workflow is defined in `.github/workflows/docker-publish.yml`. This workflow is the single source of truth for building and publishing Docker images for all services. It is responsible for:
1.  Checking out the source code.
2.  Logging into our container registry (Harbor).
3.  Building a Docker image using the specified `Dockerfile`.
4.  Tagging the image with the Git SHA of the commit.
5.  Pushing the image to the Harbor registry.

## Service Pipelines

Each service (`WebAppQ`, `H2M`, `VectorStoreQ`, `QuantumPulse`) has its own CI workflow file in the `.github/workflows/` directory. These workflows are designed to be simple and declarative.

-   **Trigger**: Each workflow is triggered by a `push` or `pull_request` to the `main` branch.
-   **Path Filtering**: A job will only run if the changes in the commit are relevant to the service's directory (or the `shared/` directory for services that use it).
-   **Action**: Each workflow calls the reusable `docker-publish.yml` workflow, passing the correct `service_name` and `dockerfile_path` for that specific service.

## Secrets

The workflows rely on the following secrets being configured in the GitHub repository's settings (`Settings > Secrets and variables > Actions`):

-   `HARBOR_URL`: The URL of the Harbor registry UI (e.g., `core.harbor.domain`).
-   `HARBOR_USER`: The username for a robot account or user with push access.
-   `HARBOR_PASSWORD`: The password for the Harbor account.

## Next Steps (GitOps)

Currently, the CI pipelines only build and publish images. The next step in maturing our DevOps process would be to implement a GitOps workflow with a tool like **ArgoCD**. This would involve:

1.  Creating a separate repository for our Kubernetes manifests (e.g., using Kustomize or Helm).
2.  Configuring ArgoCD to watch that repository.
3.  Updating our CI pipelines to automatically update the image tags in the manifests repository after a successful build.
4.  ArgoCD would then automatically detect the change and deploy the new version of the service to the Kubernetes cluster. 