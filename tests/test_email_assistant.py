"""
Pytest Evaluation Tests for Email Assistant

This module demonstrates pytest-based testing for LangGraph agents,

Tests include tool calling verification and LangSmith integration
"""

import pytest
from email_assistant.agent import compiled_email_assistant
from email_assistant.utils import extract_tool_calls
from email_assistant.eval.email_dataset import email_inputs, expected_tool_calls
from langsmith import testing as t

@pytest.mark.langsmith
@pytest.mark.parametrize("email_input, expected_calls", [
    (email_inputs[i], expected_tool_calls[i]) for i in range(len(email_inputs))
])
def test_email_dataset_tool_calls(email_input, expected_calls):
    """Test if email processing contains expected tool calls.
    
    This test confirms that all expected tools are called during email processing,
    but does not check the order of tool invocations or the number of invocations
    per tool. Additional checks for these aspects could be added if desired.
    """

    # Run the email assistant
    result = compiled_email_assistant.invoke({"email_input": email_input})

    # Extract tool calls from messages list
    extracted_tool_calls = extract_tool_calls(result['messages'])

    # Check if all expected tool calls are in the extracted ones
    missing_calls = [call for call in expected_calls if call.lower() not in extracted_tool_calls]

    # Log outputs to LangSmith
    t.log_outputs({
        "missing_calls": missing_calls,
        "extracted_tool_calls": extracted_tool_calls,
        "response": result['messages']
    })

    # Test passes if no expected calls are missing
    assert len(missing_calls) == 0