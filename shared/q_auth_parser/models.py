from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class RealmAccess(BaseModel):
    """
    Represents the roles associated with the user within a Keycloak realm.
    The 'roles' list contains strings identifying the user's assigned roles (e.g., 'admin', 'sre').
    """
    roles: List[str] = Field(default_factory=list)

class UserClaims(BaseModel):
    """
    Represents the decoded JWT claims passed by the Istio gateway.
    This model captures common OIDC and Keycloak-specific claims.
    """
    exp: int
    iat: int
    jti: str
    iss: str
    aud: List[str]
    sub: str  # The user's unique ID
    typ: str
    azp: str
    session_state: str
    acr: str
    realm_access: RealmAccess
    scope: str
    sid: str
    email_verified: bool
    name: Optional[str] = None
    preferred_username: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    email: Optional[str] = None

    def has_role(self, role: str) -> bool:
        """Checks if the user has a specific role."""
        return role in self.realm_access.roles

    class Config:
        # Allows the model to be populated even if some fields are missing from the input
        extra = "ignore" 