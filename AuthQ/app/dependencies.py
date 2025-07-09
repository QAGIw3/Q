# AuthQ/app/dependencies.py
from fastapi import Depends, HTTPException, status, Request
from keycloak import KeycloakAdmin, KeycloakOpenID
from jose import JWTError, jwt
from app.core.config import settings

def get_keycloak_admin(request: Request) -> KeycloakAdmin:
    """Dependency to get a Keycloak Admin client instance."""
    return request.app.state.keycloak_admin

def get_keycloak_openid(request: Request) -> KeycloakOpenID:
    """Dependency to get a Keycloak OpenID client instance."""
    return request.app.state.keycloak_openid

async def get_current_user(request: Request, token: str = Depends(settings.oauth2_scheme)):
    """
    Decodes the JWT token to get the current user.
    This is a simplified version. In a real system, you would also check
    token expiry, audience, and may fetch fresh user info.
    """
    try:
        # Fetch the public key from Keycloak to verify the token signature
        keycloak_openid = get_keycloak_openid(request)
        public_key = "-----BEGIN PUBLIC KEY-----\n" + keycloak_openid.public_key() + "\n-----END PUBLIC KEY-----"
        
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[settings.keycloak.algorithm],
            audience=settings.keycloak.client_id
        )
        username: str = payload.get("preferred_username")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # In a real app, you might want to return a User model here
        return {"username": username, "claims": payload}
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        ) 