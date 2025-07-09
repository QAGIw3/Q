# H2M/app/h2m_models.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class FeedbackEvent(BaseModel):
    """
    Represents a piece of feedback submitted by a user.
    This is a generic model that can be used for various types of feedback.
    """
    reference_id: str = Field(..., description="The unique ID of the item being rated (e.g., a message ID, a summary ID, a transaction ID).")
    context: str = Field(..., description="The context from which the feedback was given (e.g., 'AISummary', 'ChatResponse').")
    score: int = Field(..., description="A numerical score for the feedback, e.g., 1 for positive, -1 for negative, 0 for neutral.")
    prompt: Optional[str] = Field(None, description="The user prompt or query that led to the content being rated.")
    model_version: Optional[str] = Field(None, description="The specific version of the model that generated the content being rated.")
    feedback_text: Optional[str] = Field(None, description="Optional free-form text feedback from the user.")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Any other contextual metadata.")

class ModelMetadata(BaseModel):
    """
    Represents the metadata for a single fine-tuned model.
    """
    model_name: str = Field(..., description="The name of the model, often from the Hugging Face Hub.")
    base_model: str = Field(..., description="The original base model that was fine-tuned.")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="The timestamp of when the model was registered.")
    metrics: Optional[Dict[str, float]] = Field(None, description="Performance metrics for the model (e.g., win rate, loss).")
    tags: List[str] = Field(default_factory=list, description="Tags for categorizing or filtering models (e.g., 'summarizer', 'alpha').")

class ModelRegistryEntry(BaseModel):
    """
    Represents an entry in the model registry, linking a model name to its metadata.
    The key in the Ignite cache will be the model_name.
    """
    metadata: ModelMetadata
    is_active: bool = Field(default=False, description="Whether this model is active for routing inference requests.") 