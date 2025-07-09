import logging
from fastapi import APIRouter, Depends, HTTPException, status
from openai import OpenAI
from fastapi.responses import StreamingResponse
import json

from app.models.chat import ChatRequest, ChatResponse
from shared.q_auth_parser.parser import get_current_user
from shared.q_auth_parser.models import UserClaims
from shared.vault_client import VaultClient

# Configure logging
logger = logging.getLogger(__name__)
router = APIRouter()

# --- OpenAI Client Initialization ---
# The client is initialized upon first request to this endpoint.
# This avoids trying to connect to Vault/OpenAI at application startup.
client: OpenAI | None = None

def get_openai_client():
    """FastAPI dependency to initialize and get the OpenAI client."""
    global client
    if client is None:
        try:
            logger.info("Initializing OpenAI client for the first time.")
            vault_client = VaultClient()
            api_key = vault_client.read_secret("secret/data/openai", "api_key")
            if not api_key:
                raise ValueError("OpenAI API key not found in Vault.")
            client = OpenAI(api_key=api_key)
            logger.info("OpenAI client initialized successfully.")
        except Exception as e:
            logger.critical(f"Failed to initialize OpenAI client from Vault: {e}", exc_info=True)
            # We don't raise here, but the client will remain None,
            # and subsequent calls will fail with a 503.
    return client


async def sse_generator(openai_stream):
    """Generator function to yield Server-Sent Events from the OpenAI stream."""
    try:
        for chunk in openai_stream:
            yield f"data: {chunk.json()}\n\n"
    except Exception as e:
        logger.error(f"Error in SSE generator: {e}", exc_info=True)
        # Yield a final error message if something goes wrong
        error_payload = {"error": "An error occurred while streaming."}
        yield f"data: {json.dumps(error_payload)}\n\n"

@router.post("/completions", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def create_chat_completion(
    request: ChatRequest,
    user: UserClaims = Depends(get_current_user),
    openai_client: OpenAI = Depends(get_openai_client)
):
    """
    Provides a synchronous, request/response endpoint for chat completions.
    This acts as a centralized gateway to the underlying LLM.
    If `stream` is set to true, it returns a Server-Sent Events stream.
    """
    if not openai_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The OpenAI client is not configured or failed to initialize."
        )

    logger.info(f"Received chat completion request from user '{user.username}' for model '{request.model}'. Stream: {request.stream}")

    try:
        messages = [msg.dict() for msg in request.messages]

        # If streaming is requested, return a StreamingResponse
        if request.stream:
            stream = openai_client.chat.completions.create(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=True
            )
            return StreamingResponse(sse_generator(stream), media_type="text/event-stream")

        # Otherwise, handle as a normal synchronous request
        completion = openai_client.chat.completions.create(
            model=request.model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=False
        )
        
        response = ChatResponse(**completion.dict())
        
        logger.info(f"Successfully generated chat completion {response.id} for user '{user.username}'.")
        return response

    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while communicating with the LLM provider: {e}"
        ) 