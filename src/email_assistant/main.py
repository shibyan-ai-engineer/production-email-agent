from fastapi import FastAPI, HTTPException
from typing import Dict, Any
import uuid
import uvicorn
from .schemas import (
    ProcessEmailRequest, ProcessEmailResponse, EmailInput,
    ProcessEmailHITLRequest, ProcessEmailHITLResponse, InterruptInfo
)
from .agent import process_email
from langgraph.types import Command
from .agent_hitl import compiled_email_assistant_hitl

def _get_allowed_actions(config: Dict[str, bool]) -> list[str]:
    """Extract allowed actions from interrupt config."""
    actions = []
    if config.get("allow_accept", False):
        actions.append("accept")
    if config.get("allow_edit", False):
        actions.append("edit")
    if config.get("allow_ignore", False):
        actions.append("ignore")
    if config.get("allow_respond", False):
        actions.append("respond")
    return actions
 
def _extract_final_result(state: Dict[str, Any]) -> ProcessEmailResponse:
    """Extract final result from completed workflow state."""
    # Extract classification from state
    classification = state.get("classification_decision", "respond")
    
    # Extract response from messages
    response_text = "No response generated"
    reasoning = f"Email classified as: {classification}"
    
    # Look for the last tool execution result in messages
    messages = state.get("messages", [])
    
    # Find the most recent ToolMessage using Python best practices
    for message in reversed(messages):
        if getattr(message, 'tool_call_id', None) is not None:
            content = str(message.content)
            if "Email sent" in content or "Meeting scheduled" in content:
                response_text = content
                break
    
    return ProcessEmailResponse(
        classification=classification,
        response=response_text,
        reasoning=reasoning
    )


# Initialize FastAPI app
app = FastAPI(
    title="Email Assistant API",
    description="A complex email assistant built with LangGraph and FastAPI",
    version="1.0.0"
)


@app.get("/")
async def root() -> Dict[str, str]:
    """Basic Root check endpoint."""
    return {"message": "Email Assistant API is running!"}


@app.post("/process-email", response_model=ProcessEmailResponse)
def process_email_endpoint(request: ProcessEmailRequest)-> ProcessEmailResponse:
    """
    Process an email through the assistant agent.
    
    This endpoint takes an email and runs it through the complete workflow:
    1. Triage - determines if the email should be ignored, noted, or responded to
    2. Response - if needed, generates an appropriate response
    
    Args:
        request: ProcessEmailRequest containing the email data
        
    Returns:
        ProcessEmailResponse with classification and response
    """
    try:
        # Convert Pydantic model to dict for the agent
        email_dict = {
            "author": request.email.author,
            "to": request.email.to,
            "subject": request.email.subject,
            "email_thread": request.email.email_thread
        }

        # Process the email through the agent
        result = process_email(email_dict)

        return ProcessEmailResponse(
            classification=result["classification"],
            response=result["response"],
            reasoning=result["reasoning"]
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing email: {str(e)}"
        )
    

@app.post("/process-email-hitl", response_model=ProcessEmailHITLResponse)
async def process_email_hitl_endpoint(request: ProcessEmailHITLRequest) -> ProcessEmailHITLResponse:
    """
    Process an email through the HITL (Human-in-the-Loop) workflow.
    
    This endpoint supports both starting new HITL workflows and resuming 
    interrupted ones:
    
    **New Workflow:**
    - Provide `email` data
    - System generates thread_id and processes until interrupt
    
    **Resume Workflow:**
    - Provide `thread_id` and `human_response`
    - System resumes from interrupt point
    
    Args:
        request: HITL request with email, thread_id, and/or human_response
        
    Returns:
        HITL response with status, thread_id, and interrupt/result data
    """
    try:        
        # Determine if this is a new workflow or resume
        is_resume = request.thread_id is not None and request.human_response is not None
        is_new = request.email is not None and request.thread_id is None
        
        if not is_resume and not is_new:
            raise HTTPException(
                status_code=400,
                detail="Either provide `email` for new workflow or `thread_id` + `human_response` for resume"
            )
        
        # Generate thread config
        thread_id = request.thread_id if is_resume else str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        
        if is_new:
            # Start new HITL workflow
            email_dict = {
                "author": request.email.author,
                "to": request.email.to,
                "subject": request.email.subject,
                "email_thread": request.email.email_thread
            }
            
            # Stream until first interrupt
            for chunk in compiled_email_assistant_hitl.stream(
                {"email_input": email_dict}, 
                config=config
            ):
                if "__interrupt__" in chunk:
                    # Found interrupt - extract details
                    interrupt_data = chunk["__interrupt__"][0].value[0]
                    
                    return ProcessEmailHITLResponse(
                        status="interrupted",
                        thread_id=thread_id,
                        interrupt=InterruptInfo(
                            action=interrupt_data["action_request"]["action"],
                            args=interrupt_data["action_request"]["args"],
                            description=interrupt_data["description"],
                            allowed_actions=_get_allowed_actions(interrupt_data["config"])
                        )
                    )
                            
            # No interrupts - workflow completed
            # Get complete state instead of using streaming chunk
            complete_state = compiled_email_assistant_hitl.get_state(config)
            if complete_state and complete_state.values:
                result = _extract_final_result(complete_state.values)
                return ProcessEmailHITLResponse(
                    status="completed",
                    thread_id=thread_id,
                    result=result
                )
        
        else:
            # Resume from interrupt - add better error handling
            try:
                # Check if thread exists and has a checkpoint
                state = compiled_email_assistant_hitl.get_state(config)
                if not state or not state.values:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Thread {thread_id} not found or has no saved state"
                    )
                
                # Check if workflow is already completed
                if not state.next:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Thread {thread_id} workflow already completed. Cannot resume."
                    )
                
                human_response = request.human_response
                resume_command = Command(resume=[{
                    "type": human_response.type,
                    "args": human_response.args or {}
                }])
                
                # Continue from interrupt
                for chunk in compiled_email_assistant_hitl.stream(
                    resume_command,
                    config=config
                ):
                    if "__interrupt__" in chunk:
                        # Another interrupt occurred
                        interrupt_data = chunk["__interrupt__"][0].value[0]
                        
                        return ProcessEmailHITLResponse(
                            status="interrupted",
                            thread_id=thread_id,
                            interrupt=InterruptInfo(
                                action=interrupt_data["action_request"]["action"],
                                args=interrupt_data["action_request"]["args"],
                                description=interrupt_data["description"],
                                allowed_actions=_get_allowed_actions(interrupt_data["config"])
                            )
                        )
                                    
                # Workflow completed
                # Get complete state instead of using streaming chunk
                complete_state = compiled_email_assistant_hitl.get_state(config)
                if complete_state and complete_state.values:
                    result = _extract_final_result(complete_state.values)
                    return ProcessEmailHITLResponse(
                        status="completed",
                        thread_id=thread_id,
                        result=result
                    )
                    
            except Exception as e:
                if isinstance(e, HTTPException):
                    raise
                raise HTTPException(status_code=400, detail=f"Failed to resume thread: {str(e)}")
        
        # Fallback error
        raise HTTPException(status_code=500, detail="Unexpected workflow state")
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        
        raise HTTPException(
            status_code=500,
            detail=f"Error processing HITL email: {str(e)}"
        )
    
@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "email-assistant"}

@app.get("/process-email-hitl/{thread_id}")
async def get_hitl_thread_state(thread_id: str) -> Dict[str, Any]:
    """
    Get the current state of a HITL thread.
    
    Args:
        thread_id: The thread ID to query
        
    Returns:
        Current thread state with classification, status, and messages
    """
    try:
        config = {"configurable": {"thread_id": thread_id}}
        state = compiled_email_assistant_hitl.get_state(config)
        
        if not state or not state.values:
            raise HTTPException(
                status_code=404,
                detail=f"Thread {thread_id} not found"
            )
        
        # Extract classification from state
        classification = None
        if "classification_decision" in state.values:
            classification = state.values["classification_decision"]
        elif "triage_interrupt_handler" in state.values and isinstance(state.values["triage_interrupt_handler"], dict):
            if "classification_decision" in state.values["triage_interrupt_handler"]:
                classification = state.values["triage_interrupt_handler"]["classification_decision"]
        
        return {
            "thread_id": thread_id,
            "state": state.values,
            "classification": classification,
            "status": "interrupted" if state.next else "completed",
            "next_nodes": list(state.next) if state.next else []
        }
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving thread state: {str(e)}"
        )



if __name__ == "__main__":
    uvicorn.run(
        "src.email_assistant.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )