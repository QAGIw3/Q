resource "vault_policy" "service_policy" {
  name = "${var.service_name}-policy"
  policy = <<-EOT
    path "${var.secrets_path}" {
      capabilities = ["read"]
    }
  EOT
}

resource "vault_kubernetes_auth_backend_role" "service_role" {
  backend                          = "kubernetes"
  role_name                        = "${var.service_name}-role"
  bound_service_account_names      = [var.service_name]
  bound_service_account_namespaces = [var.namespace]
  token_policies                   = [vault_policy.service_policy.name]
  token_ttl                        = 3600
} 