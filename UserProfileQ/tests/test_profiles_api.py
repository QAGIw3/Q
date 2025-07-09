# UserProfileQ/tests/test_profiles_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import uuid
from datetime import datetime
import sys
import os

# Add the project root to the python path to allow for absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from UserProfileQ.app.main import app
from UserProfileQ.app.models.profile import ProfileModel
from shared.q_auth_parser.parser import get_current_user
from shared.q_auth_parser.models import UserClaims, RealmAccess

@pytest.fixture(scope="module")
def mock_user_claims():
    """Provides a mock authenticated user object."""
    return UserClaims(
        sub=str(uuid.uuid4()), name="testuser", email="test@example.com",
        realm_access=RealmAccess(roles=["user"]), scope="openid profile email",
        exp=9999999999, iat=9999999999, jti="test", iss="test", aud=["test"],
        typ="Bearer", azp="test", session_state="test", acr="1", sid="test",
        email_verified=True,
    )

@pytest.fixture(scope="module")
def test_app_client(mock_user_claims):
    """Creates a TestClient with the auth dependency overridden."""
    app.dependency_overrides[get_current_user] = lambda: mock_user_claims
    with TestClient(app) as client:
        yield client
    app.dependency_overrides = {}

@pytest.fixture(autouse=True)
def mock_cassandra_orm(mocker):
    """Mocks the cqlengine ORM methods to prevent real DB calls."""
    mocker.patch('UserProfileQ.app.models.profile.ProfileModel.objects')
    mocker.patch('UserProfileQ.app.models.profile.ProfileModel.create')
    mocker.patch('UserProfileQ.app.models.profile.ProfileModel.save')
    mocker.patch('cassandra.cqlengine.management.sync_table')

def test_create_user_profile_success(test_app_client, mock_user_claims):
    user_id = uuid.UUID(mock_user_claims.sub)
    ProfileModel.objects.filter.return_value.count.return_value = 0
    mock_created_instance = ProfileModel(user_id=user_id, username="testuser", email="test@example.com")
    ProfileModel.create.return_value = mock_created_instance
    profile_data = {"username": "testuser", "email": "test@example.com", "full_name": "Test User"}

    response = test_app_client.post("/api/v1/profiles/", json=profile_data)
    
    assert response.status_code == 201
    called_args, _ = ProfileModel.create.call_args
    assert called_args[0]['user_id'] == user_id

def test_create_user_profile_conflict(test_app_client, mock_user_claims):
    ProfileModel.objects.filter.return_value.count.return_value = 1
    profile_data = {"username": "testuser", "email": "test@example.com"}
    response = test_app_client.post("/api/v1/profiles/", json=profile_data)
    assert response.status_code == 409

def test_get_my_profile_success(test_app_client, mock_user_claims):
    user_id = uuid.UUID(mock_user_claims.sub)
    mock_profile = ProfileModel(user_id=user_id, username="testuser", email="test@example.com", created_at=datetime.now(), updated_at=datetime.now())
    ProfileModel.objects.get.return_value = mock_profile
    response = test_app_client.get("/api/v1/profiles/me")
    assert response.status_code == 200
    assert response.json()['user_id'] == str(user_id)

def test_get_my_profile_not_found(test_app_client):
    ProfileModel.objects.get.side_effect = ProfileModel.DoesNotExist
    response = test_app_client.get("/api/v1/profiles/me")
    assert response.status_code == 404

def test_update_my_profile_success(test_app_client, mock_user_claims):
    user_id = uuid.UUID(mock_user_claims.sub)
    mock_profile = ProfileModel(user_id=user_id, username="testuser", email="test@example.com", created_at=datetime.now(), updated_at=datetime.now())
    ProfileModel.objects.get.return_value = mock_profile
    update_data = {"full_name": "New Name", "preferences": {"theme": "dark"}}
    response = test_app_client.put("/api/v1/profiles/me", json=update_data)
    assert response.status_code == 200
    assert mock_profile.full_name == "New Name"
    mock_profile.save.assert_called_once()

def test_get_user_profile_by_id_forbidden(test_app_client):
    response = test_app_client.get(f"/api/v1/profiles/{uuid.uuid4()}")
    assert response.status_code == 403

def test_get_user_profile_by_id_as_admin(test_app_client, mock_user_claims):
    mock_user_claims.realm_access.roles.append("admin")
    target_id = uuid.uuid4()
    mock_profile = ProfileModel(user_id=target_id, username="otheruser", email="other@user.com", created_at=datetime.now(), updated_at=datetime.now())
    ProfileModel.objects.get.return_value = mock_profile
    response = test_app_client.get(f"/api/v1/profiles/{target_id}")
    assert response.status_code == 200
    assert response.json()['user_id'] == str(target_id)
    mock_user_claims.realm_access.roles.remove("admin")
