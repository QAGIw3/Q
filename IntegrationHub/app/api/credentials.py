from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict

from ..models.credential import Credential, CredentialCreate
from ..core import vault_client
from shared.q_auth_parser.parser import get_current_user
from shared.q_auth_parser.models import UserClaims

router = APIRouter()

AUTHORIZED_ROLES = {"admin"}

def check_admin_role(user: UserClaims):
    """Dependency to check if the user has the 'admin' role."""
    if "admin" not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have admin privileges for this operation."
        )

# In-memory database for demonstration purposes
credentials_db: Dict[str, Credential] = {}

@router.post("/", response_model=Credential, status_code=status.HTTP_201_CREATED, dependencies=[Depends(check_admin_role)])
def create_credential(credential_in: CredentialCreate):
    """
    Create a new credential. The secret data is stored in the vault,
    while the metadata is stored in the database. Requires admin role.
    """
    credential = Credential(**credential_in.dict(exclude={"secrets"}))
    if credential.id in credentials_db:
        raise HTTPException(status_code=400, detail=f"Credential with ID {credential.id} already exists")

    # Store the secret part in the vault
    vault_client.store_secret(credential.id, credential_in.secrets)

    # Store the non-secret part in the DB
    credentials_db[credential.id] = credential
    return credential

@router.get("/", response_model=List[Credential], dependencies=[Depends(check_admin_role)])
def list_credentials():
    """
    List all credentials (metadata only). Requires admin role.
    """
    return list(credentials_db.values())

@router.get("/{credential_id}", response_model=Credential, dependencies=[Depends(check_admin_role)])
def get_credential(credential_id: str):
    """
    Retrieve a single credential's metadata by its ID. Requires admin role.
    """
    if credential_id not in credentials_db:
        raise HTTPException(status_code=404, detail=f"Credential with ID {credential_id} not found")
    return credentials_db[credential_id]

@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(check_admin_role)])
def delete_credential(credential_id: str):
    """
    Delete a credential from the database and the vault. Requires admin role.
    """
    if credential_id not in credentials_db:
        raise HTTPException(status_code=404, detail=f"Credential with ID {credential_id} not found")

    # Delete from vault and DB
    vault_client.delete_secret(credential_id)
    del credentials_db[credential_id]
    return 