# H2M/app/h2m_models.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class FeedbackEvent(BaseModel):
    """
    Represents a piece of feedback submitted by a user.
    This is a generic model that can be used for various types of feedback.
    """
    reference_id: str = Field(..., description="The unique ID of the item being rated (e.g., a message ID, a summary ID, a transaction ID).")
    context: str = Field(..., description="The context from which the feedback was given (e.g., 'AISummary', 'ChatResponse').")
    score: int = Field(..., description="A numerical score for the feedback, e.g., 1 for positive, -1 for negative, 0 for neutral.")
    prompt: Optional[str] = Field(None, description="The user prompt or query that led to the content being rated.")
    feedback_text: Optional[str] = Field(None, description="Optional free-form text feedback from the user.")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Any other contextual metadata.") 