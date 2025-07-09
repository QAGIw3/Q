# UserProfileQ/app/api/profiles.py
import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from shared.q_auth_parser.parser import get_current_user
from shared.q_auth_parser.models import UserClaims
from UserProfileQ.app.models.profile import (
    ProfileModel,
    ProfileCreate,
    ProfileUpdate,
    ProfileResponse
)

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
def create_user_profile(
    profile_in: ProfileCreate,
    user: UserClaims = Depends(get_current_user)
):
    """
    Create a new profile for the authenticated user.
    A user can only create their own profile.
    """
    # Use the 'sub' field from the JWT as the user_id
    user_id = uuid.UUID(user.sub)

    if ProfileModel.objects.filter(user_id=user_id).count() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A profile for this user already exists.",
        )
    
    try:
        profile = ProfileModel.create(
            user_id=user_id,
            username=profile_in.username,
            email=profile_in.email,
            full_name=profile_in.full_name,
            preferences=profile_in.preferences,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        return profile.to_dict()
    except Exception as e:
        logger.error(f"Error creating profile for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create profile.")

@router.get("/me", response_model=ProfileResponse)
def get_my_profile(user: UserClaims = Depends(get_current_user)):
    """
    Retrieve the profile for the currently authenticated user.
    """
    user_id = uuid.UUID(user.sub)
    try:
        profile = ProfileModel.objects.get(user_id=user_id)
        return profile.to_dict()
    except ProfileModel.DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    except Exception as e:
        logger.error(f"Error retrieving profile for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve profile.")

@router.put("/me", response_model=ProfileResponse)
def update_my_profile(
    profile_in: ProfileUpdate,
    user: UserClaims = Depends(get_current_user)
):
    """
    Update the profile for the currently authenticated user.
    """
    user_id = uuid.UUID(user.sub)
    try:
        profile = ProfileModel.objects.get(user_id=user_id)
        
        update_data = profile_in.model_dump(exclude_unset=True)
        update_data['updated_at'] = datetime.utcnow()
        
        for key, value in update_data.items():
            setattr(profile, key, value)
        
        profile.save()
        return profile.to_dict()
    except ProfileModel.DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    except Exception as e:
        logger.error(f"Error updating profile for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not update profile.")

@router.get("/{user_id}", response_model=ProfileResponse, dependencies=[Depends(get_current_user)])
def get_user_profile_by_id(user_id: uuid.UUID, user: UserClaims = Depends(get_current_user)):
    """
    Retrieve a user's profile by their ID.
    (This is a protected endpoint, but we're not adding role checks yet)
    """
    # Future: Add role-based access control here.
    if not user.has_role("admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
    try:
        profile = ProfileModel.objects.get(user_id=user_id)
        return profile.to_dict()
    except ProfileModel.DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    except Exception as e:
        logger.error(f"Error retrieving profile for user_id {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve profile.") 