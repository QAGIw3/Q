import yaml
import hvac
import os

def migrate_config(vault_addr: str, vault_token: str, config_path: str, secret_path: str):
    """
    Migrates a YAML configuration file to Vault.
    """
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)

        client = hvac.Client(url=vault_addr, token=vault_token)
        client.secrets.kv.v2.create_or_update_secret(
            path=secret_path,
            secret=config_data,
        )
        print(f"Successfully migrated {config_path} to Vault at {secret_path}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    vault_addr = os.environ.get("VAULT_ADDR", "http://127.0.0.1:8200")
    vault_token = os.environ.get("VAULT_TOKEN")
    
    if not vault_token:
        raise ValueError("VAULT_TOKEN environment variable must be set.")

    # Migrate managerQ config
    migrate_config(
        vault_addr,
        vault_token,
        "managerQ/config/manager.yaml",
        "secret/data/managerq/config"
    )

    # Migrate agentQ config
    migrate_config(
        vault_addr,
        vault_token,
        "agentQ/config/agent.yaml",
        "secret/data/agentq/config"
    )

    # Migrate H2M config
    migrate_config(
        vault_addr,
        vault_token,
        "H2M/config/h2m.yaml",
        "secret/data/h2m/config"
    )

    # Migrate VectorStoreQ config
    migrate_config(
        vault_addr,
        vault_token,
        "VectorStoreQ/config/vectorstore.yaml",
        "secret/data/vectorstore/config"
    )

    # Migrate QuantumPulse config
    migrate_config(
        vault_addr,
        vault_token,
        "QuantumPulse/config/quantumpulse.yaml",
        "secret/data/quantumpulse/config"
    ) 