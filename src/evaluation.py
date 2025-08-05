"""
Agent Evaluation System

This module implements LLM-as-judge evaluation

Provides structured evaluation of email assistant responses using GPT-4o
with the CriteriaGrade
"""
from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field
from email_assistant.eval.email_dataset import email_inputs, response_criteria_list
from email_assistant.utils import format_messages_string
from email_assistant.agent import compiled_email_assistant
from email_assistant.prompts import RESPONSE_CRITERIA_SYSTEM_PROMPT



# Exact schema for evaluation
class CriteriaGrade(BaseModel):
    """Score the response against specific criteria."""
    justification: str = Field(description="The justification for the grade and score, including specific examples from the response.")
    grade: bool = Field(description="Does the response meet the provided criteria?")

# Create global LLM for evaluation
criteria_eval_llm = init_chat_model("openai:gpt-4o")
criteria_eval_structured_llm = criteria_eval_llm.with_structured_output(CriteriaGrade)


def run_llm_as_judge_evaluation():
    """
    Run LLM-as-judge evaluation for evaluating
    response quality using structured LLM grading.
    """

    print("🧠 Running LLM-as-Judge Evaluation")
    print("=" * 40)

    # Use first email example
    email_input = email_inputs[1]
    success_criteria = response_criteria_list[1]
    

    # Invoke email assistant 
    response = compiled_email_assistant.invoke({"email_input": email_input})
    messages = response['messages']

     # Format messages into string 
    all_messages_str = format_messages_string(messages)

     # LLM-as-judge evaluation with structured output
    eval_result = criteria_eval_structured_llm.invoke([
        {"role": "system", "content": RESPONSE_CRITERIA_SYSTEM_PROMPT},
        {"role": "user", "content": f"""\n\n Response criteria: {success_criteria} \n\n Assistant's response: \n\n {all_messages_str} \n\n Evaluate whether the assistant's response meets the criteria and provide justification for your evaluation."""}
    ])

    print("\n📊 Evaluation Result:")
    print(f"Grade: {'PASS' if eval_result.grade else 'FAIL'}")
    print(f"Justification: {eval_result.justification}")
    
    return eval_result


if __name__ == "__main__":
    # Run the LLM-as-judge evaluation 
    run_llm_as_judge_evaluation()