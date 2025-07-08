from fastapi import APIRouter, HTTPException, status
from typing import List, Dict

from ..models.credential import Credential, CredentialCreate
from ..core import vault_client

router = APIRouter()

# In-memory database for demonstration purposes
credentials_db: Dict[str, Credential] = {}

@router.post("/", response_model=Credential, status_code=status.HTTP_201_CREATED)
def create_credential(credential_in: CredentialCreate):
    """
    Create a new credential. The secret data is stored in the vault,
    while the metadata is stored in the database.
    """
    credential = Credential(**credential_in.dict(exclude={"secrets"}))
    if credential.id in credentials_db:
        raise HTTPException(status_code=400, detail=f"Credential with ID {credential.id} already exists")

    # Store the secret part in the vault
    vault_client.store_secret(credential.id, credential_in.secrets)

    # Store the non-secret part in the DB
    credentials_db[credential.id] = credential
    return credential

@router.get("/", response_model=List[Credential])
def list_credentials():
    """
    List all credentials (metadata only).
    """
    return list(credentials_db.values())

@router.get("/{credential_id}", response_model=Credential)
def get_credential(credential_id: str):
    """
    Retrieve a single credential's metadata by its ID.
    """
    if credential_id not in credentials_db:
        raise HTTPException(status_code=404, detail=f"Credential with ID {credential_id} not found")
    return credentials_db[credential_id]

@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_credential(credential_id: str):
    """
    Delete a credential from the database and the vault.
    """
    if credential_id not in credentials_db:
        raise HTTPException(status_code=404, detail=f"Credential with ID {credential_id} not found")

    # Delete from vault and DB
    vault_client.delete_secret(credential_id)
    del credentials_db[credential_id]
    return 