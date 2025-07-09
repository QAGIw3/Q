# AuthQ/app/core/config.py
from pydantic import BaseSettings
from fastapi.security import OAuth2PasswordBearer

class KeycloakSettings(BaseSettings):
    server_url: str
    client_id: str
    realm_name: str
    admin_username: str
    admin_password: str
    client_secret: str
    algorithm: str = "RS256"

class Settings(BaseSettings):
    service_name: str = "AuthQ"
    keycloak: KeycloakSettings

    class Config:
        # This allows loading the settings from a nested dictionary,
        # which is how they might be stored in Vault.
        env_nested_delimiter = '__'

settings = Settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token") 