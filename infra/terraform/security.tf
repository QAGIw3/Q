# This file contains the Istio and Vault security configurations for the Q Platform.

# --- Istio Service Mesh Security ---

# 1. RequestAuthentication: Tells the ingress gateway how to validate JWTs.
resource "kubernetes_manifest" "jwt_validator" {
  manifest = {
    "apiVersion" = "security.istio.io/v1"
    "kind"       = "RequestAuthentication"
    "metadata" = {
      "name"      = "jwt-validator"
      # This policy applies to the default istio-system namespace where the gateway lives
      "namespace" = "istio-system"
    }
    "spec" = {
      "selector" = {
        "matchLabels" = {
          "istio" = "ingressgateway"
        }
      }
      "jwtRules" = [
        {
          "issuer"               = var.keycloak_issuer_url
          "jwksUri"              = "${var.keycloak_issuer_url}/protocol/openid-connect/certs"
          "outputPayloadToHeader" = "X-User-Claims"
          "forwardOriginalToken" = true
        }
      ]
    }
  }
}

# 2. AuthorizationPolicy: Enforces that a valid JWT is required for all requests.
resource "kubernetes_manifest" "require_jwt" {
  manifest = {
    "apiVersion" = "security.istio.io/v1"
    "kind"       = "AuthorizationPolicy"
    "metadata" = {
      "name"      = "require-jwt-for-q-platform"
      # This policy applies to the namespace where our services are deployed
      "namespace" = "q-platform"
    }
    "spec" = {
      # By default, this applies to all workloads in the namespace
      "action" = "ALLOW"
      "rules" = [
        {
          "from" = [
            {
              "source" = {
                # This requires that the request principal is not empty,
                # which means the JWT was successfully validated by the
                # RequestAuthentication policy.
                "requestPrincipals" = ["*"]
              }
            }
          ]
        }
      ]
    }
  }
  depends_on = [helm_release.keycloak]
}

# --- Vault Kubernetes Integration ---

# 1. Enable the Kubernetes auth method in Vault.
resource "vault_auth_backend" "kubernetes" {
  type = "kubernetes"
  path = "kubernetes"
}

# 2. Configure the Kubernetes auth method.
# This tells Vault how to communicate with the Kubernetes API.
resource "vault_kubernetes_auth_backend_config" "k8s_config" {
  backend         = vault_auth_backend.kubernetes.path
  kubernetes_host = "https://kubernetes.default.svc"
  # In a real cluster, you would securely provide the CA cert and a token reviewer JWT.
  # For this setup, we will rely on the service account token mounted in the Vault pod.
  # This requires proper RBAC permissions for the Vault service account.
}

# --- Service-Specific Vault Roles ---

module "managerq_vault_role" {
  source       = "./modules/vault-service-role"
  service_name = "managerq"
  namespace    = var.namespace
}

module "agentq_vault_role" {
  source       = "./modules/vault-service-role"
  service_name = "agentq"
  namespace    = var.namespace
}

module "integrationhub_vault_role" {
  source       = "./modules/vault-service-role"
  service_name = "integrationhub"
  namespace    = var.namespace
}

module "knowledgegraphq_vault_role" {
  source       = "./modules/vault-service-role"
  service_name = "knowledgegraphq"
  namespace    = var.namespace
}

# Add other service modules as needed... 