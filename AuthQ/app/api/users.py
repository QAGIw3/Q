# AuthQ/app/api/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from keycloak import KeycloakAdmin
from keycloak.exceptions import KeycloakPostError

from app.models.user import UserCreate, User
from app.dependencies import get_keycloak_admin, get_current_user

router = APIRouter()

@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
def create_user(
    user_data: UserCreate,
    keycloak_admin: KeycloakAdmin = Depends(get_keycloak_admin)
):
    """
    Registers a new user in the Keycloak realm.
    """
    try:
        new_user = keycloak_admin.create_user({
            "username": user_data.username,
            "email": user_data.email,
            "firstName": user_data.first_name,
            "lastName": user_data.last_name,
            "enabled": True,
            "credentials": [{"type": "password", "value": user_data.password, "temporary": False}],
        }, exist_ok=False)
        
        # Keycloak returns the new user's ID
        # We need to fetch the full user representation to return it
        created_user_id = new_user
        user_info = keycloak_admin.get_user(created_user_id)

        return User(
            id=user_info['id'],
            username=user_info['username'],
            email=user_info['email'],
            first_name=user_info.get('firstName'),
            last_name=user_info.get('lastName'),
            enabled=user_info['enabled'],
            email_verified=user_info.get('emailVerified', False),
            created_timestamp=user_info.get('createdTimestamp', 0)
        )

    except KeycloakPostError as e:
        # User might already exist
        if e.response_code == 409:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A user with username '{user_data.username}' or email '{user_data.email}' already exists.",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred with Keycloak: {e.error_message}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}",
        ) 