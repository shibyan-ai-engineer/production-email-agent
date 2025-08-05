"""Email assistant agent with Human-in-the-Loop (HITL) capabilities."""

import os
from typing import Literal
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START, END
from langgraph.store.base import BaseStore
from langgraph.store.redis import RedisStore
from langgraph.types import Command, interrupt
from langgraph.checkpoint.redis import RedisSaver
from dotenv import load_dotenv

from .tools import get_tools, get_tools_by_name
from .tools.default.prompt_templates import HITL_TOOLS_PROMPT
from .prompts import (
    TRIAGE_SYSTEM_PROMPT, 
    TRIAGE_USER_PROMPT,
    AGENT_SYSTEM_PROMPT_HITL,
    DEFAULT_BACKGROUND,
    DEFAULT_TRIAGE_INSTRUCTIONS,
    DEFAULT_RESPONSE_PREFERENCES,
    DEFAULT_CAL_PREFERENCES,
    MEMORY_UPDATE_INSTRUCTIONS,
    MEMORY_UPDATE_INSTRUCTIONS_REINFORCEMENT
)
from .schemas import State, RouterSchema, StateInput, UserPreferences
from .utils import parse_email, format_email_markdown, format_for_display

# CRITICAL: Load environment variables before LLM initialization
load_dotenv()

# Get tools
tools = get_tools(["write_email", "schedule_meeting", "check_calendar_availability", "Question", "Done"])
tools_by_name = get_tools_by_name(tools)

# Initialize LLM with low temperature for consistent responses
llm = init_chat_model("openai:gpt-4.1", temperature=0.0)

# Create specialized LLM for structured triage decisions
llm_router = llm.with_structured_output(RouterSchema)

# Initialize the LLM, enforcing tool use (of any available tools) for agent
llm_with_tools = llm.bind_tools(tools, tool_choice="required")


def get_memory(store, namespace, default_content=None):
    """Get memory from the store or initialize with default if it doesn't exist.
    
    Args:
        store: LangGraph BaseStore instance to search for existing memory
        namespace: Tuple defining the memory namespace, e.g. ("email_assistant", "triage_preferences")
        default_content: Default content to use if memory doesn't exist
        
    Returns:
        str: The content of the memory profile, either from existing memory or the default
    """
    # Search for existing memory with namespace and key
    user_preferences = store.get(namespace, "user_preferences")

    print(f"Searching for user preferences in namespace {namespace}...")
    # If memory exists, return its content (the value)
    if user_preferences:
        return user_preferences.value
    
    # If memory doesn't exist, add it to the store and return the default content
    else:
        # Namespace, key, value
        store.put(namespace, "user_preferences", default_content)
        user_preferences = default_content
    
    print("final_user_preferences:", user_preferences)
    # Return the default content
    return user_preferences 


def update_memory(store, namespace, messages):
    """Update memory profile in the store.
    
    Args:
        store: LangGraph BaseStore instance to update memory
        namespace: Tuple defining the memory namespace, e.g. ("email_assistant", "triage_preferences")
        messages: List of messages to update the memory with
    """
    # Get the existing memory
    user_preferences = store.get(namespace, "user_preferences")
    # Handle case where memory doesn't exist yet
    current_profile = user_preferences.value if user_preferences else "No existing preferences"
    # Update the memory
    llm_memory = init_chat_model("openai:gpt-4.1", temperature=0.0).with_structured_output(UserPreferences)
    result = llm_memory.invoke(
        [
            {"role": "system", "content": MEMORY_UPDATE_INSTRUCTIONS.format(current_profile=current_profile, namespace=namespace)},
        ] + messages
    )

    print("to_update_final_user_preferences:", result)

    # Save the updated memory to the store
    store.put(namespace, "user_preferences", result.user_preferences)


def triage_router(state: State, store: BaseStore) -> Command[Literal["triage_interrupt_handler", "response_agent", "__end__"]]:
    """Analyze email content to decide if we should respond, notify, or ignore.
    
    HITL Enhancement: When classification is 'notify', route to interrupt handler
    instead of ending immediately.
    """
    
    author, to, subject, email_thread = parse_email(state["email_input"])
    
    # Format prompts with dynamic context
    # Search for existing triage_preferences memory
    triage_instructions = get_memory(store, ("email_assistant", "triage_preferences"), DEFAULT_TRIAGE_INSTRUCTIONS)
    
    # Format system prompt with background and triage instructions
    system_prompt = TRIAGE_SYSTEM_PROMPT.format(
        background=DEFAULT_BACKGROUND,
        triage_instructions=triage_instructions
    )

    # Format user prompt with email details
    user_prompt = TRIAGE_USER_PROMPT.format(
        author=author, to=to, subject=subject, email_thread=email_thread
    )

    # Get structured classification from LLM
    result = llm_router.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ])
    
    # Decision
    classification = result.classification
    
    email_markdown = format_email_markdown(subject, author, to, email_thread)
    
    # Process the classification decision
    if classification == "respond":
        print("📧 Classification: RESPOND - This email requires a response")
        # Next node
        goto = "response_agent"
        # Update the state
        update = {
            "classification_decision": classification,
            "messages": [{"role": "user",
                            "content": f"Respond to the email: {email_markdown}"
                        }],
        }
        
    elif classification == "ignore":
        print("🚫 Classification: IGNORE - This email can be safely ignored")
        # Next node
        goto = END
        # Update the state
        update = {
            "classification_decision": classification,
        }
        
    elif classification == "notify":
        print("🔔 Classification: NOTIFY - This email contains important information") 
        # This is new! 
        goto = "triage_interrupt_handler"
        # Update the state
        update = {
            "classification_decision": classification,
        }
        
    else:
        raise ValueError(f"Invalid classification: {classification}")
        
    return Command(goto=goto, update=update)


def triage_interrupt_handler(state: State, store: BaseStore) -> Command[Literal["response_agent", "__end__"]]:
    """Handle interrupts from the triage step when email is classified as 'notify'.
    
    This allows humans to review notification emails and decide whether to:
    - Ignore the email (end workflow)
    - Provide feedback to respond to the email (continue to response agent)
    """
    
    # Parse the email input for display
    author, to, subject, email_thread = parse_email(state["email_input"])
    email_markdown = format_email_markdown(subject, author, to, email_thread)

    # Create messages for the response agent if user chooses to respond
    messages = [{
        "role": "user",
        "content": f"Email to notify user about: {email_markdown}"
    }]

    # Create interrupt request for Agent Inbox display
    request = {
        "action_request": {
            "action": f"Email Assistant: {state['classification_decision']}",
            "args": {}
        },
        "config": {
            "allow_ignore": True,   # User can ignore the notification
            "allow_respond": True,  # User can provide feedback to respond
            "allow_edit": False,    # No editing needed for notifications
            "allow_accept": False,  # No acceptance needed for notifications
        },
        # Email content to show in Agent Inbox
        "description": email_markdown,
    }

    # Interrupt execution and wait for human input
    response = interrupt([request])[0]

    # Process human response
    if response["type"] == "response":
        # User wants to respond - add their feedback to messages
        user_input = response["args"]
        messages.append({
            "role": "user",
            "content": f"User wants to reply to the email. Use this feedback to respond: {user_input}"
        })
        # Update memory with feedback
        update_memory(store, ("email_assistant", "triage_preferences"), [{
            "role": "user",
            "content": f"The user decided to respond to the email, so update the triage preferences to capture this."
        }] + messages)
        goto = "response_agent"

    elif response["type"] == "ignore":
        # Make note of the user's decision to ignore the email
        messages.append({
            "role": "user",
            "content": f"The user decided to ignore the email even though it was classified as notify. Update triage preferences to capture this."
        })
        # Update memory with feedback 
        update_memory(store, ("email_assistant", "triage_preferences"), messages)
        goto = END

    else:
        raise ValueError(f"Invalid response type: {response}")

    # Update state with messages for response agent AND preserve classification
    update = {
        "messages": messages,
        "classification_decision": state["classification_decision"]  # Preserve original classification
    }
    return Command(goto=goto, update=update)


def llm_call(state: State, store: BaseStore):
    """LLM decides which tool to call using HITL-enabled prompt."""
    
    # Search for existing cal_preferences memory
    cal_preferences = get_memory(store, ("email_assistant", "cal_preferences"), DEFAULT_CAL_PREFERENCES)
    
    # Search for existing response_preferences memory
    response_preferences = get_memory(store, ("email_assistant", "response_preferences"), DEFAULT_RESPONSE_PREFERENCES)
    
    # Format system prompt with all context
    system_prompt = AGENT_SYSTEM_PROMPT_HITL.format(
        tools_prompt=HITL_TOOLS_PROMPT,
        background=DEFAULT_BACKGROUND,
        response_preferences=response_preferences,
        cal_preferences=cal_preferences,
    )
    
    return {
        "messages": [
            llm_with_tools.invoke([
                {"role": "system", "content": system_prompt}
            ] + state["messages"])
        ]
    }


def interrupt_handler(state: State, store: BaseStore) -> Command[Literal["llm_call", "__end__"]]:
    """Core HITL component: Handle human review of tool calls.
    
    This is the heart of the HITL system. It:
    1. Categorizes tools into HITL (require approval) vs auto-execute
    2. Creates interrupts for human review of sensitive tools
    3. Processes human responses: accept, edit, ignore, or provide feedback
    4. Maintains message thread consistency across interrupt/resume cycles
    """
    
    result = []
    goto = "llm_call"  # Default: continue to LLM after processing

    # Process each tool call from the LLM
    for tool_call in state["messages"][-1].tool_calls:
        
        # Define which tools require human approval
        hitl_tools = ["write_email", "schedule_meeting", "Question"]
        
        # Auto-execute non-HITL tools without interruption
        if tool_call["name"] not in hitl_tools:
            tool = tools_by_name[tool_call["name"]]
            observation = tool.invoke(tool_call["args"])
            result.append({
                "role": "tool", 
                "content": str(observation), 
                "tool_call_id": tool_call["id"]
            })
            continue
            
        # HITL tools require human review
        # Get original email context for display
        email_input = state["email_input"]
        author, to, subject, email_thread = parse_email(email_input)
        original_email_markdown = format_email_markdown(subject, author, to, email_thread)
        
        # Format tool call for clear display in Agent Frontend UI
        tool_display = format_for_display(tool_call)
        description = original_email_markdown + tool_display

        # Configure allowed actions based on tool type
        if tool_call["name"] == "write_email":
            config = {
                "allow_ignore": True,    # User can cancel email
                "allow_respond": True,   # User can provide feedback
                "allow_edit": True,      # User can edit email content
                "allow_accept": True,    # User can approve as-is
            }
        elif tool_call["name"] == "schedule_meeting":
            config = {
                "allow_ignore": True,    # User can cancel meeting
                "allow_respond": True,   # User can provide feedback
                "allow_edit": True,      # User can edit meeting details
                "allow_accept": True,    # User can approve as-is
            }
        elif tool_call["name"] == "Question":
            config = {
                "allow_ignore": True,    # User can skip question
                "allow_respond": True,   # User can answer question
                "allow_edit": False,     # Questions can't be edited
                "allow_accept": False,   # Questions need answers, not acceptance
            }
        else:
            raise ValueError(f"Unexpected HITL tool: {tool_call['name']}")

        # Create interrupt request
        request = {
            "action_request": {
                "action": tool_call["name"],
                "args": tool_call["args"]
            },
            "config": config,
            "description": description,
        }

        # Interrupt execution and wait for human response
        response = interrupt([request])[0]

        # Process human response
        if response["type"] == "accept":
            # Execute tool with original arguments
            tool = tools_by_name[tool_call["name"]]
            observation = tool.invoke(tool_call["args"])
            result.append({
                "role": "tool", 
                "content": str(observation), 
                "tool_call_id": tool_call["id"]
            })
                        
        elif response["type"] == "edit":
            # Execute tool with edited arguments
            tool = tools_by_name[tool_call["name"]]
            edited_args = response["args"]["args"]

            # Update the AI message's tool call with edited content (reference to the message in the state)
            ai_message = state["messages"][-1]  # Get the most recent message from the state
            current_id = tool_call["id"]  # Store the ID of the tool call being edited
            
            # Create a new list of tool calls by filtering out the one being edited and adding the updated version
            # This avoids modifying the original list directly (immutable approach)
            updated_tool_calls = [tc for tc in ai_message.tool_calls if tc["id"] != current_id] + [
                {"type": "tool_call", "name": tool_call["name"], "args": edited_args, "id": current_id}
            ]
            
            # Create a new copy of the message with updated tool calls rather than modifying the original
            # This ensures state immutability and prevents side effects in other parts of the code
            # When we update the messages state key ("messages": result), the add_messages reducer will
            # overwrite existing messages by id and we take advantage of this here to update the tool calls.
            result.append(ai_message.model_copy(update={"tool_calls": updated_tool_calls}))

            # Update the write_email tool call with the edited content from Agent Inbox
            if tool_call["name"] == "write_email":
                # Store initial tool call for memory update
                initial_tool_call = tool_call["args"]
                # Execute the tool with edited args
                observation = tool.invoke(edited_args)
                # Add only the tool response message
                result.append({"role": "tool", "content": observation, "tool_call_id": current_id})
                # Update memory with feedback
                update_memory(store, ("email_assistant", "response_preferences"), [{
                    "role": "user",
                    "content": f"User edited the email response. Here is the initial email generated by the assistant: {initial_tool_call}. Here is the edited email: {edited_args}. Follow all instructions above, and remember: {MEMORY_UPDATE_INSTRUCTIONS_REINFORCEMENT}."
                }])
            
            # Update the schedule_meeting tool call with the edited content from Agent Inbox
            elif tool_call["name"] == "schedule_meeting":
                # Store initial tool call for memory update
                initial_tool_call = tool_call["args"]
                # Execute the tool with edited args
                observation = tool.invoke(edited_args)
                # Add only the tool response message
                result.append({"role": "tool", "content": observation, "tool_call_id": current_id})
                # Update memory with feedback
                update_memory(store, ("email_assistant", "cal_preferences"), [{
                    "role": "user",
                    "content": f"User edited the calendar invitation. Here is the initial calendar invitation generated by the assistant: {initial_tool_call}. Here is the edited calendar invitation: {edited_args}. Follow all instructions above, and remember: {MEMORY_UPDATE_INSTRUCTIONS_REINFORCEMENT}."
                }])
            
            # Catch all other tool calls
            else:
                raise ValueError(f"Invalid tool call: {tool_call['name']}")

        elif response["type"] == "ignore":
            if tool_call["name"] == "write_email":
                # Don't execute the tool, and tell the agent how to proceed
                result.append({"role": "tool", "content": "User ignored this email draft. Ignore this email and end the workflow.", "tool_call_id": tool_call["id"]})
                # Go to END
                goto = END
                # Update memory
                update_memory(store, ("email_assistant", "triage_preferences"), state["messages"] + result + [{
                    "role": "user",
                    "content": f"The user ignored the email draft. That means they did not want to respond to the email. Update the triage preferences to ensure emails of this type are not classified as respond. Follow all instructions above, and remember: {MEMORY_UPDATE_INSTRUCTIONS_REINFORCEMENT}."
                }])
            elif tool_call["name"] == "schedule_meeting":
                # Don't execute the tool, and tell the agent how to proceed
                result.append({"role": "tool", "content": "User ignored this calendar meeting draft. Ignore this email and end the workflow.", "tool_call_id": tool_call["id"]})
                # Go to END
                goto = END
                # Update memory
                update_memory(store, ("email_assistant", "triage_preferences"), state["messages"] + result + [{
                    "role": "user",
                    "content": f"The user ignored the calendar meeting draft. That means they did not want to schedule a meeting for this email. Update the triage preferences to ensure emails of this type are not classified as respond. Follow all instructions above, and remember: {MEMORY_UPDATE_INSTRUCTIONS_REINFORCEMENT}."
                }])
            elif tool_call["name"] == "Question":
                # Don't execute the tool, and tell the agent how to proceed
                result.append({"role": "tool", "content": "User ignored this question. Ignore this email and end the workflow.", "tool_call_id": tool_call["id"]})
                # Go to END
                goto = END
                # Update memory
                update_memory(store, ("email_assistant", "triage_preferences"), state["messages"] + result + [{
                    "role": "user",
                    "content": f"The user ignored the Question. That means they did not want to answer the question or deal with this email. Update the triage preferences to ensure emails of this type are not classified as respond. Follow all instructions above, and remember: {MEMORY_UPDATE_INSTRUCTIONS_REINFORCEMENT}."
                }])
            else:
                raise ValueError(f"Invalid tool call: {tool_call['name']}")
            
        elif response["type"] == "response":
            # User provided feedback
            user_feedback = response["args"]
            if tool_call["name"] == "write_email":
                # Don't execute the tool, and add a message with the user feedback to incorporate into the email
                result.append({"role": "tool", "content": f"User gave feedback, which can we incorporate into the email. Feedback: {user_feedback}", "tool_call_id": tool_call["id"]})
                # Update memory
                update_memory(store, ("email_assistant", "response_preferences"), state["messages"] + result + [{
                    "role": "user",
                    "content": f"User gave feedback, which we can use to update the response preferences. Follow all instructions above, and remember: {MEMORY_UPDATE_INSTRUCTIONS_REINFORCEMENT}."
                }])
            elif tool_call["name"] == "schedule_meeting":
                # Don't execute the tool, and add a message with the user feedback to incorporate into the meeting request
                result.append({"role": "tool", "content": f"User gave feedback, which can we incorporate into the meeting request. Feedback: {user_feedback}", "tool_call_id": tool_call["id"]})
                # Update memory
                update_memory(store, ("email_assistant", "cal_preferences"), state["messages"] + result + [{
                    "role": "user",
                    "content": f"User gave feedback, which we can use to update the calendar preferences. Follow all instructions above, and remember: {MEMORY_UPDATE_INSTRUCTIONS_REINFORCEMENT}."
                }])
            elif tool_call["name"] == "Question": 
                # Don't execute the tool, and add a message with the user feedback to incorporate into the email
                result.append({"role": "tool", "content": f"User answered the question, which can we can use for any follow up actions. Feedback: {user_feedback}", "tool_call_id": tool_call["id"]})
            else:
                raise ValueError(f"Invalid tool call: {tool_call['name']}")

        else:
            raise ValueError(f"Invalid response type: {response}")
            
    # Update state with processed messages
    update = {"messages": result}
    return Command(goto=goto, update=update)


def should_continue(state: State, store: BaseStore) -> Literal["interrupt_handler", "__end__"]:
    """Route to tool handler, or end if Done tool called"""
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        for tool_call in last_message.tool_calls: 
            if tool_call["name"] == "Done":
                return END
            else:
                return "interrupt_handler"
    return END


# Build the HITL response agent (subgraph for tool-calling with human oversight)
response_agent = StateGraph(State)
response_agent.add_node("llm_call", llm_call) 
response_agent.add_node("interrupt_handler", interrupt_handler)

response_agent.add_edge(START, "llm_call")
response_agent.add_conditional_edges(
    "llm_call",
    should_continue,
    {
        "interrupt_handler": "interrupt_handler",
        END: END,
    },
)
# After interrupt handling, loop back to LLM for next action
response_agent.add_edge("interrupt_handler", "llm_call")

compiled_response_agent = response_agent.compile()

# Build the overall HITL workflow
email_assistant_hitl = StateGraph(State, input=StateInput)
email_assistant_hitl.add_node("triage_router", triage_router)
email_assistant_hitl.add_node("triage_interrupt_handler", triage_interrupt_handler)
email_assistant_hitl.add_node("response_agent", compiled_response_agent)

email_assistant_hitl.add_edge(START, "triage_router")
# Note: triage_router uses Command for conditional routing

def get_compiled_email_assistant_hitl():
    """Get compiled HITL email assistant with Redis context management.
    
    This function uses proper context managers for Redis components as recommended
    in the LangGraph documentation for memory persistence.
    
    Returns:
        Compiled StateGraph with Redis store and checkpointer
    """
    # Get Redis URL from environment variable, fallback to localhost for development
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    with RedisStore.from_conn_string(redis_url) as store, \
         RedisSaver.from_conn_string(redis_url) as checkpointer:
        store.setup()
        checkpointer.setup()
        return email_assistant_hitl.compile(checkpointer=checkpointer, store=store)

# For backward compatibility, provide the compiled agent directly
compiled_email_assistant_hitl = get_compiled_email_assistant_hitl()