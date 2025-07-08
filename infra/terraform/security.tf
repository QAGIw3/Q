# This file contains the Istio security configurations for the Q Platform.

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