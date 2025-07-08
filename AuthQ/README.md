# AuthQ - Security & Identity Management

## Overview

AuthQ is the centralized security service for the Q Platform. It is responsible for managing and enforcing authentication and authorization for all users, developers, and services, establishing a zero-trust security model.

## Key Components

| Component             | Technology                                                                          | Purpose                                                                                                                                                                                          |
|-----------------------|-------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Identity Provider** | [Keycloak](https://www.keycloak.org/)                                               | An open-source Identity and Access Management solution. It will act as the central OIDC-compliant authority for user identities, role-based access control (RBAC), and issuing JWT access tokens. |
| **API Gateway**       | [Istio Ingress Gateway](https://istio.io/latest/docs/tasks/traffic-management/ingress/ingress-control/) | Istio's built-in gateway will serve as the single, managed entry point for all external API traffic. It will be configured to intercept requests, validate JWTs, and enforce coarse-grained access policies. |
| **Service Mesh**      | [Istio](https://istio.io/)                                                          | Deployed as the platform's service mesh to secure all internal service-to-service communication. It will automatically enforce mutual TLS (mTLS), ensuring that all traffic is encrypted and authenticated. |

## Authentication & Security Flow

1.  **User Login**: A user authenticates against Keycloak.
2.  **Token Issuance**: Keycloak issues a JWT access token.
3.  **API Request**: The client includes the JWT in the `Authorization` header of requests to the Istio Ingress Gateway.
4.  **Gateway Validation**: The Istio Gateway, using a `RequestAuthentication` and `AuthorizationPolicy`, validates the JWT and ensures the user has rights to access the requested service.
5.  **Internal Request (mTLS)**: Once inside the mesh, all subsequent service-to-service calls (e.g., `H2M` to `agentQ`) are automatically wrapped in mutual TLS encryption by the Istio sidecar proxies, ensuring zero-trust networking.

## Enabling the Service Mesh

To enable Istio's automatic mTLS and traffic management for our services, the Kubernetes namespace where the Q Platform is deployed must be labeled. This instructs Istio to automatically inject its sidecar proxy into every pod deployed in that namespace.

```bash
# Label the 'q-platform' namespace for Istio sidecar injection
kubectl label namespace q-platform istio-injection=enabled
```

## Roadmap

- Deploy a highly available Keycloak cluster.
- Configure realms, clients, and roles for the Q Platform.
- Choose and deploy an API Gateway and integrate it with Keycloak.
- Configure Istio `AuthorizationPolicy` resources for fine-grained, service-level access control.
- Roll out the service mesh across the Kubernetes cluster.
- Develop libraries for services to easily extract user context from JWTs. 