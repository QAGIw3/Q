# AuthQ - Security & Identity Management

## Overview

AuthQ is the centralized security service for the Q Platform. It is responsible for managing and enforcing authentication and authorization for all users, developers, and services, establishing a zero-trust security model.

## Key Components

| Component             | Technology                                                                          | Purpose                                                                                                                                                                                          |
|-----------------------|-------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Identity Provider** | [Keycloak](https://www.keycloak.org/)                                               | An open-source Identity and Access Management solution. It will act as the central OIDC-compliant authority for user identities, role-based access control (RBAC), and issuing JWT access tokens. |
| **API Gateway**       | [Kong](https://konghq.com/kong/), [Traefik](https://traefik.io/), or similar         | A single, managed entry point for all external API traffic. The gateway will be configured to intercept all requests, validate the JWT from Keycloak, and enforce coarse-grained access policies.  |
| **Service Mesh**      | [Istio](https://istio.io/) or [Linkerd](https://linkerd.io/)                        | For securing all internal service-to-service communication within the Kubernetes cluster. It will automatically enforce mutual TLS (mTLS), ensuring that all traffic is encrypted and authenticated. |

## Authentication Flow

1.  **User Login**: A user or developer authenticates against Keycloak via a UI or OAuth 2.0 flow.
2.  **Token Issuance**: Keycloak issues a short-lived JWT access token containing the user's ID, roles, and permissions.
3.  **API Request**: The user's client application includes this JWT in the `Authorization` header of every request to the platform's API Gateway.
4.  **Gateway Validation**: The API Gateway intercepts the request, validates the JWT's signature and claims, and ensures the user has the basic rights to access the requested endpoint.
5.  **Internal Request**: The request is forwarded to the appropriate microservice (e.g., `H2M`).
6.  **Service-to-Service**: If `H2M` needs to call another service, the request is transparently encrypted and authenticated by the service mesh (Istio/Linkerd), which handles mTLS and fine-grained authorization policies.

## Roadmap

- Deploy a highly available Keycloak cluster.
- Configure realms, clients, and roles for the Q Platform.
- Choose and deploy an API Gateway and integrate it with Keycloak.
- Roll out the service mesh across the Kubernetes cluster.
- Develop libraries for services to easily extract user context from JWTs. 