from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langchain.chat_models import init_chat_model
from email_assistant.schemas import State, RouterSchema
from email_assistant.utils import parse_email, format_email_markdown
from email_assistant.prompts import (TRIAGE_SYSTEM_PROMPT, DEFAULT_BACKGROUND, DEFAULT_TRIAGE_INSTRUCTIONS, TRIAGE_USER_PROMPT, AGENT_SYSTEM_PROMPT, DEFAULT_RESPONSE_PREFERENCES, DEFAULT_CAL_PREFERENCES)
from dotenv import load_dotenv
from email_assistant.agent_tools import TOOLS
from IPython.display import Image, display
from typing import Literal


# Load environment variables first
load_dotenv()

# Initialize LLM
llm = init_chat_model("openai:gpt-4.1", temperature=0.0)

# Create router llm with structured output
llm_router = llm.with_structured_output(RouterSchema)

# Create tool-enabled LLM for response generation
tools_by_name = {tool.name: tool for tool in TOOLS}
llm_with_tools = llm.bind_tools(TOOLS, tool_choice="any")

def triage_router(state: State):
    """Analyze email content to decide if we should respond, notify, or ignore."""
    # print("INcoming State: ", state)
    # parse email
    author, to, subject, email_thread = parse_email(state["email_input"])

    system_prompt = TRIAGE_SYSTEM_PROMPT.format(background=DEFAULT_BACKGROUND, triage_instructions=DEFAULT_TRIAGE_INSTRUCTIONS)

    user_prompt = TRIAGE_USER_PROMPT.format(
        author=author, to=to, subject=subject, email_thread=email_thread
    )

    result = llm_router.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ])

    print(f"📋 Email Triage: {result.classification.upper()}")

    if result.classification == "respond":
        print("📧 Routing to response agent...")
        goto = "response_agent"
        update = {
            "classification_decision": result.classification,
            "messages": [{
                "role": "user",
                "content": f"Respond to the email: \n\n{format_email_markdown(subject, author, to, email_thread)}",
            }]
        }

    elif result.classification == "ignore":
        print("🚫 Email will be ignored")
        goto= END
        update = {"classification_decision": result.classification}
    elif result.classification == "notify":
        print("🔔 Email marked for notification only")
        goto= END
        update = {"classification_decision": result.classification}
    else:
        raise ValueError(f"Invalid classification: {result.classification}") 

    return Command(goto=goto, update=update)

def llm_call(state: State):
    """LLM decides which tool to call or if processing is complete."""
    system_prompt = AGENT_SYSTEM_PROMPT.format(
        background=DEFAULT_BACKGROUND,
        response_preferences=DEFAULT_RESPONSE_PREFERENCES,
        cal_preferences=DEFAULT_CAL_PREFERENCES, 
    )

    # Combine system prompt with conversation history
    return {
        "messages": [
            llm_with_tools.invoke([
                {"role": "system", "content": system_prompt}
            ] + state["messages"])
        ]
    }

def tool_handler(state: State):
    """Execute the tool calls from the LLM."""
    last_message = state["messages"][-1]
    result = []

    # Execute each tool call and capture results
    for tool_call in last_message.tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        result.append({
            "role": "tool", 
            "content": str(observation), 
            "tool_call_id": tool_call["id"]  # Required for LLM to track tool results
        })
        print(f"🔧 Tool executed: {tool_call['name']}")
    
    return {"messages": result}

def should_continue(state: State) -> Literal["tool_handler", "__end__"]:
    """Determine if we should continue with tools or end processing."""
    
    last_message = state["messages"][-1]
    
    if last_message.tool_calls:
        # Special handling for Done tool - signals completion
        for tool_call in last_message.tool_calls:
            if tool_call["name"] == "Done":
                print("✅ Processing complete")
                return END
        return "tool_handler"
    
    return END

# Build the response agent (subgraph for handling tool-calling workflow)
response_agent = StateGraph(State)
response_agent.add_node("llm_call", llm_call)
response_agent.add_node("tool_handler", tool_handler)

response_agent.add_edge(START, "llm_call")
# Conditional routing: continue with tools or finish
response_agent.add_conditional_edges(
    "llm_call",
    should_continue,
    {
        "tool_handler": "tool_handler",
        END: END,
    },
)

# Loop back to LLM after tool execution
response_agent.add_edge("tool_handler", "llm_call")

compiled_response_agent = response_agent.compile()



# # Build the overall workflow (main graph)
email_assistant = StateGraph(State)
email_assistant.add_node("triage_router", triage_router)
email_assistant.add_node("response_agent", compiled_response_agent)

email_assistant.add_edge(START, "triage_router")
# Note: triage_router uses Command to handle conditional routing


# Compile the final agent
compiled_email_assistant = email_assistant.compile()


def process_email(email_input: dict) -> dict:
    """
    Process an email through the complete workflow.
    
    Args:
        email_input: Dictionary with keys: author, to, subject, email_thread
        
    Returns:
        Dictionary with processing results
    """
    result = compiled_email_assistant.invoke({"email_input": email_input})

    # Extract meaningful response from the conversation
    response_text = "No response generated"

    if result.get("messages"):
        # Look for the actual email content in tool calls (write_email tool)
        for message in result["messages"]:
            # Check if this is an assistant message with tool calls
            if (hasattr(message, 'tool_calls') and message.tool_calls):
                for tool_call in message.tool_calls:
                    if tool_call.get('name') == 'write_email':
                        # Extract the email content from the tool arguments
                        args = tool_call.get('args', {})
                        email_content = args.get('content', '')
                        if email_content:
                            response_text = email_content
                            break
                if response_text != "No response generated":
                    break
            # Fallback: look for assistant messages with actual content
            elif (hasattr(message, 'role') and message.role == "assistant" and 
                  hasattr(message, 'content') and message.content.strip()):
                response_text = message.content
                break

    return {
        "classification": result.get("classification_decision", "unknown"),
        "response": response_text,
        "reasoning": f"Email classified as: {result.get('classification_decision', 'unknown')}"
    }




# if __name__ == "__main__":
#     process_email({
#     "author": "Alice <alice@company.com>",
#     "to": "John <john@company.com>", 
#     "subject": "Question about API",
#     "email_thread": "Hi! I have a question about the API documentation. Could we schedule a quick call this week?"
#   })