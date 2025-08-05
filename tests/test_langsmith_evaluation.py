from email_assistant.agent import compiled_email_assistant
from email_assistant.eval.email_dataset import examples_triage
from langsmith import Client
import os

def target_email_assistant(inputs: dict):
    """Process an email through the workflow-based email assistant."""
    response = compiled_email_assistant.nodes['triage_router'].invoke({"email_input": inputs["email_input"]})
    return {"classification_decision": response.update['classification_decision']}

def classification_evaluator(outputs: dict, reference_outputs: dict) -> bool:
    """Check if the answer exactly matches the expected answer.
    """
    return outputs["classification_decision"].lower() == reference_outputs["classification"].lower()

def create_evaluation_dataset():
    """
    Create a LangSmith dataset for email evaluation.
    
    """
    client = Client()
    dataset_name = "E-mail Triage Evaluation"
    
    # Create dataset if it doesn't exist
    if not client.has_dataset(dataset_name=dataset_name):
        dataset = client.create_dataset(
            dataset_name=dataset_name, 
            description="A dataset of e-mails and their triage decisions."
        )
        # Add examples to the dataset
        client.create_examples(dataset_id=dataset.id, examples=examples_triage)
    
    return dataset_name


def run_langsmith_evaluation():
    " Run evaluation using LangSm ith Dataset"

    client = Client()
    dataset_name = create_evaluation_dataset()
    
    print(f"🔍 Running evaluation against dataset: {dataset_name}")
    
    # Run evaluation 
    experiment_results = client.evaluate(
        # Run agent 
        target_email_assistant,
        # Evaluator
        evaluators=[classification_evaluator], # we can pass multiple evaluators
        # Dataset name   
        data=dataset_name,
        # Name of the experiment
        experiment_prefix="E-mail assistant workflow", 
        # Number of concurrent evaluations
        max_concurrency=10, 
    )

if __name__ == "__main__":
    print("🚀 LangSmith Evaluation Demo")
    print("=" * 40)
    
    if os.getenv("LANGSMITH_API_KEY"):
        result = run_langsmith_evaluation()
        if result:
            print(f"View results at: https://smith.langchain.com/")
    else:
        print("⚠️  Set LANGSMITH_API_KEY environment variable to run LangSmith evaluation")
        print("This is optional - you can complete the tutorial without LangSmith")