# Continuous Integration & Deployment (CI/CD)

This document outlines the CI/CD strategy for the Q Platform, which is built on GitHub Actions and ArgoCD to achieve a fully automated GitOps workflow.

## The GitOps Workflow

Our CI/CD process automatically builds, publishes, and deploys our services. Here's how it works:

1.  A developer pushes a change to the `main` branch.
2.  The appropriate service-specific workflow is triggered (e.g., `h2m-ci.yml`).
3.  This workflow calls the reusable `docker-publish.yml` workflow.
4.  **Build & Push**: The `docker-publish` job builds a new Docker image, tags it with the Git commit SHA, and pushes it to our Harbor registry.
5.  **Update Manifest**: After the image is pushed, the `update-manifest` job is triggered. It calls the reusable `kustomize-edit.yml` workflow.
6.  **Commit & Trigger**: The `kustomize-edit` job automatically checks out the repository, runs `kustomize edit set image ...` to update the image tag in our Kubernetes manifests, and pushes the change back to the `main` branch.
7.  **Deploy**: ArgoCD, running in our Kubernetes cluster, detects the change in the manifests repository and automatically syncs the new configuration, deploying the updated service.

## Reusable Workflows

-   **`docker-publish.yml`**: The main CI workflow that orchestrates the build and manifest update steps.
-   **`kustomize-edit.yml`**: A specialized workflow responsible for safely editing our Kustomize manifests to update image tags.

## Service Pipelines

Each service (`WebAppQ`, `H2M`, etc.) has its own CI workflow file that calls the main `docker-publish.yml` workflow with the correct parameters for that service. They are triggered by changes in their respective directories.

## Secrets

The workflows rely on the following secrets being configured in the GitHub repository's settings (`Settings > Secrets and variables > Actions`):

-   **Registry Credentials**:
    -   `HARBOR_URL`: The URL of the Harbor registry.
    -   `HARBOR_USER`: The username for a robot account.
    -   `HARBOR_PASSWORD`: The password for the Harbor account.
-   **Git Credentials** (for pushing manifest changes):
    -   `GIT_USER_NAME`: The name of the Git user for commits (e.g., "Q Platform CI").
    -   `GIT_USER_EMAIL`: The email of the Git user.
    -   `GIT_ACCESS_TOKEN`: A GitHub Personal Access Token with `repo` scope to allow pushing changes to the repository. 