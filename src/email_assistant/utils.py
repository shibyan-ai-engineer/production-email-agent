from typing import List, Tuple, Any

def parse_email(email_input: dict) -> Tuple[str, str, str, str]:
    """Parse email input dictionary into components.
    
    Args:
        email_input: Dictionary with keys: author, to, subject, email_thread
        
    Returns:
        Tuple of (author, to, subject, email_thread)
    """
    return (
        email_input.get("author", ""),
        email_input.get("to", ""),
        email_input.get("subject", ""),
        email_input.get("email_thread", "")
    )

def format_email_markdown(subject: str, author: str, to: str, email_thread: str) -> str:
    """Format email details into a markdown string for display.
    
    Args:
        subject: Email subject
        author: Email sender
        to: Email recipient
        email_thread: Email content
        
    Returns:
        Formatted markdown string
    """
    return f"""**Subject**: {subject}
**From**: {author}
**To**: {to}

{email_thread}

---
"""


def extract_tool_calls(messages: List[Any]) -> List[str]:
    """Extract tool call names from a list of messages.
    
    Args:
        messages: List of message objects
        
    Returns:
        List of tool names that were called
    """
    tool_calls = []
    
    for message in messages:
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(tc['name'].lower())
    
    return tool_calls

def format_messages_string(messages: List[Any]) -> str:
    """Format a list of messages into a readable string.
    
    Args:
        messages: List of message objects
        
    Returns:
        Formatted string representation of messages
    """
    formatted_messages = []
    
    for message in messages:
        role = getattr(message, 'role', 'unknown')
        content = getattr(message, 'content', str(message))
        
        if hasattr(message, 'tool_calls') and message.tool_calls:
            tool_calls = [f"{tc['name']}({tc['args']})" for tc in message.tool_calls]
            content += f" [Tools: {', '.join(tool_calls)}]"
            
        formatted_messages.append(f"{role.upper()}: {content}")
    
    return "\n\n".join(formatted_messages)


def format_for_display(tool_call):
    """Format content for display in Agent Inbox
    
    Args:
        tool_call: The tool call to format
    """
    # Initialize empty display
    display = ""
    
    # Add tool call information
    if tool_call["name"] == "write_email":
        display += f"""# Email Draft

**To**: {tool_call["args"].get("to")}
**Subject**: {tool_call["args"].get("subject")}

{tool_call["args"].get("content")}
"""
    elif tool_call["name"] == "schedule_meeting":
        display += f"""# Calendar Invite

**Meeting**: {tool_call["args"].get("subject")}
**Attendees**: {', '.join(tool_call["args"].get("attendees"))}
**Duration**: {tool_call["args"].get("duration_minutes")} minutes
**Day**: {tool_call["args"].get("preferred_day")}
"""
    elif tool_call["name"] == "Question":
        # Special formatting for questions to make them clear
        display += f"""# Question for User

{tool_call["args"].get("content")}
"""
    else:
        # Generic format for other tools
        display += f"""# Tool Call: {tool_call["name"]}

Arguments:"""
        
        # Check if args is a dictionary or string
        if isinstance(tool_call["args"], dict):
            display += f"\n{json.dumps(tool_call['args'], indent=2)}\n"
        else:
            display += f"\n{tool_call['args']}\n"
    return display