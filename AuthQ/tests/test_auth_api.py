# AuthQ/tests/test_auth_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.main import app
from app.dependencies import get_keycloak_admin, get_keycloak_openid

# Fixture to create a mock Keycloak admin client
@pytest.fixture
def mock_keycloak_admin():
    mock = MagicMock()
    # Mock the create_user method to return a dummy user ID
    mock.create_user.return_value = "new-user-id-123"
    # Mock get_user to return a full user dict
    mock.get_user.return_value = {
        'id': 'new-user-id-123',
        'username': 'testuser',
        'email': 'test@example.com',
        'firstName': 'Test',
        'lastName': 'User',
        'enabled': True,
        'emailVerified': False,
        'createdTimestamp': 1678886400000
    }
    return mock

# Fixture to create a mock Keycloak OpenID client
@pytest.fixture
def mock_keycloak_openid():
    mock = MagicMock()
    # Mock the token method to return a dummy access token
    mock.token.return_value = {"access_token": "dummy-access-token"}
    return mock

# Override the dependencies with our mock clients
@pytest.fixture(autouse=True)
def override_dependencies(mock_keycloak_admin, mock_keycloak_openid):
    app.dependency_overrides[get_keycloak_admin] = lambda: mock_keycloak_admin
    app.dependency_overrides[get_keycloak_openid] = lambda: mock_keycloak_openid
    yield
    app.dependency_overrides = {}


client = TestClient(app)

def test_register_user_success():
    """Test successful user registration."""
    response = client.post(
        "/api/v1/users/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "strongpassword",
            "first_name": "Test",
            "last_name": "User"
        }
    )
    assert response.status_code == 201
    user_data = response.json()
    assert user_data["username"] == "testuser"
    assert user_data["email"] == "test@example.com"
    assert user_data["id"] == "new-user-id-123"

def test_login_for_access_token_success():
    """Test successful token acquisition."""
    response = client.post(
        "/api/v1/auth/token",
        json={"username": "testuser", "password": "password"}
    )
    assert response.status_code == 200
    token_data = response.json()
    assert token_data["access_token"] == "dummy-access-token"
    assert token_data["token_type"] == "bearer"

def test_register_user_conflict(mock_keycloak_admin):
    """Test user registration conflict (user already exists)."""
    from keycloak.exceptions import KeycloakPostError
    mock_keycloak_admin.create_user.side_effect = KeycloakPostError(
        response_code=409, error_message="User already exists"
    )
    
    response = client.post(
        "/api/v1/users/register",
        json={"username": "testuser", "email": "test@example.com", "password": "password"}
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]

def test_login_for_access_token_failure(mock_keycloak_openid):
    """Test failed token acquisition due to bad credentials."""
    mock_keycloak_openid.token.side_effect = Exception("Invalid credentials")
    
    response = client.post(
        "/api/v1/auth/token",
        json={"username": "wronguser", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert "Invalid username or password" in response.json()["detail"] 