# DevOps Platform & GitOps

## Overview

This service provides the CI/CD and GitOps foundation for the Q Platform. Its purpose is to fully automate the build, testing, and deployment lifecycle of all microservices, enabling rapid, reliable, and auditable releases.

## Key Components

| Component               | Technology                                       | Purpose                                                                                                                                                                                           |
|-------------------------|--------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **CI Pipeline**         | [GitHub Actions](https://github.com/features/actions) or [GitLab CI](https://docs.gitlab.com/ee/ci/) | To automatically build, test, and lint code on every commit. Pipelines will produce versioned container images and push them to the container registry.                                           |
| **Container Registry**  | [Harbor](https://goharbor.io/)                   | A private, secure, and cloud-native registry to store, scan, and sign container images produced by the CI pipeline. It provides vulnerability scanning and project-level isolation.            |
| **GitOps Controller**   | [ArgoCD](https://argo-cd.readthedocs.io/)        | A declarative, GitOps continuous delivery tool for Kubernetes. It monitors a Git repository containing the desired state of all applications and automatically syncs the live state to match it. |

## Workflow

1.  **Commit**: A developer pushes code to a feature branch in a service's repository (e.g., `H2M`).
2.  **Pull Request**: A PR triggers a CI pipeline in GitHub Actions. The pipeline runs linting, unit tests, and builds a candidate container image.
3.  **Merge**: Upon PR approval and merge to `main`, a new CI pipeline runs, tags a versioned image, and pushes it to Harbor.
4.  **Deploy**: The developer updates the application version in the central GitOps repository.
5.  **Sync**: ArgoCD detects the change in the GitOps repository and automatically pulls the new container image from Harbor, deploying it to the appropriate Kubernetes environment (e.g., staging or production).

## Roadmap

- Set up a production-grade Harbor instance.
- Develop standardized CI pipeline templates for Python and other potential service languages.
- Deploy ArgoCD and structure the GitOps repository.
- Implement environment promotion strategies (e.g., dev -> staging -> prod). 