"""Pydantic models and type definitions for the email assistant."""
from langgraph.graph import MessagesState
from typing_extensions import TypedDict, Literal
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any



class EmailInput(BaseModel):
    """Input schema for email data."""
    
    author: str = Field(description="Email sender")
    to: str = Field(description="Email recipient")
    subject: str = Field(description="Email subject line")
    email_thread: str = Field(description="Email content/body")

class RouterSchema(BaseModel):
    """Schema for email triage routing decisions."""
    
    reasoning: str = Field(
        description="Step-by-step reasoning behind the classification."
    )
    classification: Literal["ignore", "respond", "notify"] = Field(
        description="The classification of an email: 'ignore' for irrelevant emails, "
        "'notify' for important information that doesn't need a response, "
        "'respond' for emails that need a reply",
    )


class State(MessagesState):
    """State schema for the email assistant agent.
    
    Extends MessagesState to include email-specific data.
    """
    email_input: dict
    classification_decision: Literal["ignore", "respond", "notify"]

class StateInput(TypedDict):
    # This is the input to the state
    email_input: dict

class EmailData(TypedDict):
    id: str
    thread_id: str
    from_email: str
    subject: str
    page_content: str
    send_time: str
    to_email: str

class ProcessEmailRequest(BaseModel):
    """Request schema for processing emails via API."""
    
    email: EmailInput
    

class ProcessEmailResponse(BaseModel):
    """Response schema for email processing."""
    
    classification: Literal["ignore", "respond", "notify"]
    response: str
    reasoning: str


# HITL-specific schemas
class HumanResponse(BaseModel):
    """Schema for human responses in HITL workflows."""
    
    type: Literal["accept", "edit", "ignore", "response"] = Field(
        description="Type of human response"
    )
    args: Optional[Any] = Field(
        default=None,
        description="Arguments for edit/response actions"
    )


class InterruptInfo(BaseModel):
    """Information about an interrupt requiring human input."""
    
    action: str = Field(description="The tool/action that triggered the interrupt")
    args: Dict[str, Any] = Field(description="Original arguments for the action")
    description: str = Field(description="Human-readable description of the action")
    allowed_actions: List[str] = Field(description="List of allowed human response types")


class ProcessEmailHITLRequest(BaseModel):
    """Request schema for HITL email processing."""
    
    email: Optional[EmailInput] = Field(
        default=None,
        description="Email data (required for new workflows)"
    )
    thread_id: Optional[str] = Field(
        default=None,
        description="Thread ID for resuming existing workflows"
    )
    human_response: Optional[HumanResponse] = Field(
        default=None,
        description="Human response to resume from interrupt"
    )


class ProcessEmailHITLResponse(BaseModel):
    """Response schema for HITL email processing."""
    
    status: Literal["interrupted", "completed", "error"] = Field(
        description="Status of the workflow"
    )
    thread_id: str = Field(description="Thread ID for this workflow")
    interrupt: Optional[InterruptInfo] = Field(
        default=None,
        description="Interrupt details when status=interrupted"
    )
    result: Optional[ProcessEmailResponse] = Field(
        default=None,
        description="Final result when status=completed"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message when status=error"
    )

class UserPreferences(BaseModel):
    """Updated user preferences based on user's feedback."""
    chain_of_thought: str = Field(description="Reasoning about which user preferences need to add/update if required")
    user_preferences: str = Field(description="Updated user preferences")