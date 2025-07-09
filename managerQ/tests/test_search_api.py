# managerQ/tests/test_search_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock

from managerQ.app.main import app
from managerQ.app.dependencies import get_vector_store_client, get_kg_client, get_pulse_client
from shared.q_auth_parser.parser import get_current_user
from shared.q_vectorstore_client.models import SearchResponse as VectorSearchResponse, QueryResult, SearchHit
from shared.q_pulse_client.models import QPChatResponse, QPChatChoice, QPChatMessage

# Mock data for external services
MOCK_VECTOR_SEARCH_RESULT = VectorSearchResponse(
    results=[
        QueryResult(
            hits=[
                SearchHit(
                    id="doc1",
                    score=0.95,
                    metadata={"source": "/docs/test.md", "text": "This is a test document."}
                )
            ]
        )
    ]
)

MOCK_KG_RESULT = {
    "result": {
        "data": [
            {
                "@type": "g:Vertex",
                "@value": {
                    "id": "node1",
                    "label": "Service",
                    "properties": {
                        "name": [
                            {"@type": "g:Property", "@value": {"key": "name", "value": "managerQ"}}
                        ]
                    }
                }
            }
        ]
    }
}

MOCK_PULSE_RESPONSE = QPChatResponse(
    choices=[QPChatChoice(message=QPChatMessage(role="assistant", content="This is an AI summary."))]
)

# Fixtures for mock clients
@pytest.fixture
def mock_vector_store():
    return AsyncMock(search=AsyncMock(return_value=MOCK_VECTOR_SEARCH_RESULT))

@pytest.fixture
def mock_kg_client():
    mock = AsyncMock()
    mock.execute_gremlin_query.return_value = MOCK_KG_RESULT
    return mock

@pytest.fixture
def mock_pulse_client():
    return AsyncMock(get_chat_completion=AsyncMock(return_value=MOCK_PULSE_RESPONSE))

# Override dependencies
@pytest.fixture(autouse=True)
def override_dependencies(mock_vector_store, mock_kg_client, mock_pulse_client):
    app.dependency_overrides[get_vector_store_client] = lambda: mock_vector_store
    app.dependency_overrides[get_kg_client] = lambda: mock_kg_client
    app.dependency_overrides[get_pulse_client] = lambda: mock_pulse_client
    app.dependency_overrides[get_current_user] = lambda: {"username": "testuser", "roles": ["admin"]}
    yield
    app.dependency_overrides = {}

client = TestClient(app)

def test_cognitive_search_success():
    """Test successful cognitive search orchestration."""
    response = client.post("/v1/search/", json={"query": "test query"})

    assert response.status_code == 200
    data = response.json()

    # Check AI summary
    assert data["ai_summary"] == "This is an AI summary."

    # Check vector results
    assert len(data["vector_results"]) == 1
    assert data["vector_results"][0]["content"] == "This is a test document."
    assert data["vector_results"][0]["source"] == "/docs/test.md"

    # Check KG results
    assert len(data["knowledge_graph_result"]["nodes"]) == 1
    assert data["knowledge_graph_result"]["nodes"][0]["id"] == "node1"
    assert data["knowledge_graph_result"]["nodes"][0]["label"] == "Service"

def test_cognitive_search_kg_fails(mock_kg_client):
    """Test when the knowledge graph service fails."""
    mock_kg_client.execute_gremlin_query.side_effect = Exception("KG connection failed")

    response = client.post("/v1/search/", json={"query": "test query"})

    assert response.status_code == 200
    data = response.json()

    # Should still return results from other services
    assert data["ai_summary"] is not None
    assert len(data["vector_results"]) == 1
    # KG result should be None
    assert data["knowledge_graph_result"] is None 