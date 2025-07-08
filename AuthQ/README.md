# AuthQ - Security & Identity Management

## Overview

AuthQ is the centralized security service for the Q Platform. It is responsible for managing and enforcing authentication and authorization for all users, developers, and services, establishing a zero-trust security model. It is not a single service, but a pattern of using **Keycloak** for identity and **Istio** for enforcement.

## Key Components

| Component             | Technology                                                                          | Purpose                                                                                                                                                                                          |
|-----------------------|-------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Identity Provider** | [Keycloak](https://www.keycloak.org/)                                               | An open-source Identity and Access Management solution. It acts as the central OIDC-compliant authority for user identities, role-based access control (RBAC), and issuing JWT access tokens.      |
| **API Gateway**       | [Istio Ingress Gateway](https://istio.io/latest/docs/tasks/traffic-management/ingress/ingress-control/) | Istio's built-in gateway serves as the single, managed entry point for all external API traffic. It is configured to intercept requests, validate JWTs, and enforce coarse-grained access policies.   |
| **Service Mesh**      | [Istio](https://istio.io/)                                                          | Deployed as the platform's service mesh to secure all internal service-to-service communication. It automatically enforces mutual TLS (mTLS), ensuring that all traffic is encrypted and authenticated. |
| **Shared Library**    | `q_auth_parser`                                                                     | A local shared library (`shared/q_auth_parser`) that provides a standard, easy-to-use method for services to access user claims after they have been validated by the gateway.                    |

## Authentication & Security Flow

1.  **User Login**: A user authenticates against Keycloak via a frontend application.
2.  **Token Issuance**: Keycloak issues a signed JWT access token.
3.  **API Request**: The client includes the JWT in the `Authorization` header of all requests to the Istio Ingress Gateway.
4.  **Gateway Validation**: The Istio Gateway intercepts the request. Using a `RequestAuthentication` resource, it validates the JWT's signature against Keycloak's public keys.
5.  **Claim Forwarding**: Upon successful validation, the gateway forwards the request to the target service, adding the JWT's payload (the claims) as a new, base64-encoded request header (e.g., `X-User-Claims`).
6.  **Service Logic**: The service uses the `q_auth_parser` library to easily decode and validate the claims from the header into a clean Pydantic object, making user ID and roles available to its business logic.
7.  **Internal Communication (mTLS)**: All subsequent service-to-service calls are automatically encrypted and authenticated via Istio's mTLS, ensuring zero-trust networking.

---

## Service Integration (`q_auth_parser`)

Services within the mesh **should not** validate JWTs themselves. They should trust the gateway and simply consume the claims. The `q_auth_parser` library makes this trivial.

### Installation

```bash
# From the root of the Q project, install the library in editable mode
pip install -e ./shared/q_auth_parser
```

### Usage in a REST API (HTTP Headers)

Use the `get_user_claims` dependency in your standard API endpoints.

```python
from fastapi import APIRouter, Depends
from q_auth_parser.parser import get_user_claims
from q_auth_parser.models import UserClaims

router = APIRouter()

@router.get("/my-protected-data")
async def get_my_data(claims: UserClaims = Depends(get_user_claims)):
    # If the code reaches here, the claims are valid.
    # You can now use the user's identity securely.
    
    user_id = claims.sub
    user_email = claims.email
    
    if "admin" in claims.realm_access.roles:
        # Perform admin-only logic
        return {"message": f"Hello Admin {user_email}!"}
        
    return {"message": f"Hello User {user_email}!"}
```

### Usage in a WebSocket API (Query Parameters)

For WebSockets, the authentication information must be passed during the initial handshake. Use the `get_user_claims_ws` dependency, which reads the claims from a query parameter.

```python
from fastapi import APIRouter, Depends
from q_auth_parser.parser import get_user_claims_ws
from q_auth_parser.models import UserClaims
from fastapi import WebSocket

router = APIRouter()

@router.websocket("/ws/my-protected-socket")
async def my_socket(
    websocket: WebSocket,
    claims: UserClaims = Depends(get_user_claims_ws)
):
    await websocket.accept()
    # You now have the user's identity via the 'claims' object
    user_id = claims.sub
    user_email = claims.email
    
    if "admin" in claims.realm_access.roles:
        # Perform admin-only logic
        await websocket.send_text(f"Hello Admin {user_email}!")
    else:
        await websocket.send_text(f"Hello User {user_email}!")
```

A client would connect with a URL like:
`ws://<host>/ws/my-protected-socket?claims=<base64-encoded-claims>`

---

## Istio Configuration Examples

These YAML configurations are applied to the Kubernetes cluster to enable the security flow.

### 1. JWT Validation (`RequestAuthentication`)

This resource tells the Istio Ingress Gateway how to validate JWTs. It specifies the Keycloak issuer and the location of the public keys (JWKS).

```yaml
# istio-request-auth.yaml
apiVersion: security.istio.io/v1
kind: RequestAuthentication
metadata:
  name: "jwt-validator"
  namespace: istio-system
spec:
  selector:
    matchLabels:
      istio: ingressgateway
  jwtRules:
  - issuer: "https://keycloak.your-domain.com/realms/your-realm"
    jwksUri: "https://keycloak.your-domain.com/realms/your-realm/protocol/openid-connect/certs"
    # The header where the validated claims payload will be placed
    outputPayloadToHeader: "X-User-Claims"
```

### 2. Access Enforcement (`AuthorizationPolicy`)

This policy mandates that all requests to services in the `q-platform` namespace must have a valid JWT, as validated by the `jwt-validator` `RequestAuthentication`.

```yaml
# istio-auth-policy.yaml
apiVersion: security.istio.io/v1
kind: AuthorizationPolicy
metadata:
  name: "require-jwt"
  namespace: q-platform # Apply this policy to our main namespace
spec:
  action: ALLOW
  rules:
  - from:
    - source:
        requestPrincipals: ["*"] # Allows any valid JWT
```

---

## Roadmap

- Deploy a highly available Keycloak cluster.
- Configure realms, clients, and roles for the Q Platform.
- Apply the `RequestAuthentication` and `AuthorizationPolicy` resources to the cluster.
- Roll out the service mesh by labeling the `q-platform` namespace for Istio sidecar injection.
- Integrate the `q_auth_parser` library into all relevant services. 