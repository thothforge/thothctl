import asyncio
import json
from functools import partial
from typing import Any, Callable, Dict, Optional, Union

import boto3
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.prompts import PromptTemplate
from langchain_aws import BedrockLLM
from langchain_community.chat_models import BedrockChat, ChatOpenAI
from langchain_ollama import OllamaLLM


def read_tfplan(file_path: str) -> Dict[str, Any]:
    """Read and parse a Terraform plan file."""
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        raise Exception(f"Error reading tfplan.json: {str(e)}")


def create_analysis_prompt() -> PromptTemplate:
    """Create the analysis prompt template."""
    template = """
    You are a security expert. Analyze the following Terraform plan for security risks 
    and compliance issues. Focus on:

    1. Security Groups and Network Security:
       - Overly permissive security group rules
       - Public exposure of sensitive services
       - Unsafe port configurations

    2. Access Management:
       - IAM roles and permissions
       - Resource policies
       - Authentication configurations

    3. Data Security:
       - Encryption settings
       - Sensitive data handling
       - Storage configuration

    4. Compliance and Best Practices:
       - Resource naming conventions
       - Tagging compliance
       - Architecture best practices

    Terraform Plan:
    {plan_json}

    Provide a detailed analysis with:
    - Identified risks
    - Severity level for each risk (HIGH/MEDIUM/LOW)
    - Specific resource references
    - Recommended remediation steps
    """
    return PromptTemplate(input_variables=["plan_json"], template=template)


def initialize_ollama_model(
    model_name: str = "llama3",
    temperature: float = 0.7,
    base_url: str = "http://localhost:11434",
) -> OllamaLLM:
    """Initialize Ollama model."""
    return OllamaLLM(model=model_name, temperature=temperature, base_url=base_url)


def initialize_bedrock_model(
    model_name: str, temperature: float, region: str, profile: Optional[str] = None
):
    """Initialize a Bedrock model."""
    session = boto3.Session(profile_name=profile, region_name=region)
    client = session.client("bedrock-runtime")

    model_map = {
        "claude": "anthropic.claude-v2",
        "claude-instant": "anthropic.claude-instant-v1",
        "titan": "amazon.titan-text-express-v1",
        "jurassic": "ai21.j2-ultra-v1",
    }

    model_id = model_map.get(model_name.lower(), model_name)

    if "claude" in model_id.lower():
        return BedrockChat(
            client=client, model_id=model_id, model_kwargs={"temperature": temperature}
        )
    return BedrockLLM(
        client=client, model_id=model_id, model_kwargs={"temperature": temperature}
    )


def initialize_model(
    model_type: str,
    model_name: str,
    temperature: float = 0.7,
    region: Optional[str] = None,
    profile: Optional[str] = None,
    base_url: str = "http://localhost:11434",
):
    """Initialize the appropriate language model."""
    if model_type.lower() == "ollama":
        return initialize_ollama_model(model_name, temperature, base_url)

    elif model_type.lower() == "openai":
        return ChatOpenAI(model_name=model_name, temperature=temperature)

    elif model_type.lower() == "bedrock":
        if not region:
            raise ValueError("AWS region is required for Bedrock")
        return initialize_bedrock_model(model_name, temperature, region, profile)

    raise ValueError(f"Unsupported model type: {model_type}")


def analyze_risks(llm: Any, tfplan_path: str, stream: bool = False) -> Union[str, None]:
    """Analyze risks in the Terraform plan."""
    try:
        plan_data = read_tfplan(tfplan_path)
        prompt = create_analysis_prompt()

        formatted_prompt = prompt.format(plan_json=json.dumps(plan_data, indent=2))

        if stream:
            callbacks = [StreamingStdOutCallbackHandler()]
            response = llm.generate([formatted_prompt], callbacks=callbacks)
            return None

        response = llm.generate([formatted_prompt])
        return response.generations[0][0].text

    except Exception as e:
        return f"Error during analysis: {str(e)}"


async def analyze_risks_async(llm: Any, tfplan_path: str) -> str:
    """Analyze risks asynchronously."""
    try:
        plan_data = read_tfplan(tfplan_path)
        prompt = create_analysis_prompt()

        formatted_prompt = prompt.format(plan_json=json.dumps(plan_data, indent=2))

        response = await llm.agenerate([formatted_prompt])
        return response.generations[0][0].text

    except Exception as e:
        return f"Error during analysis: {str(e)}"


def create_analyzer(
    model_type: str,
    model_name: str,
    temperature: float = 0.7,
    region: Optional[str] = None,
    profile: Optional[str] = None,
    base_url: str = "http://localhost:11434",
) -> Callable:
    """Create a partially applied analyze_risks function with the specified model."""
    llm = initialize_model(
        model_type, model_name, temperature, region, profile, base_url
    )
    return partial(analyze_risks, llm)


# Example usage
if __name__ == "__main__":
    # Create an analyzer using Ollama
    analyze_with_ollama = create_analyzer(
        model_type="ollama",
        model_name="llama3.1",
        base_url="http://localhost:11434",  # Default Ollama URL
    )

    # Create an analyzer using Bedrock
    analyze_with_bedrock = create_analyzer(
        model_type="bedrock",
        model_name="meta.llama3-1-70b-instruct-v1:0",
        temperature=0.7,
        region="us-east-2",
        profile="labvel-dev",
    )

    # Example tfplan path
    tfplan_path = "tfplan.json"

    # Regular analysis
    print("Analyzing with locally Ollama:")
    results = analyze_with_ollama(tfplan_path)
    print(results)

    # Streaming analysis
    # print("\nStreaming analysis with Ollama:")
    # analyze_with_ollama(tfplan_path, stream=True)
    print("Analyzing with Bedrock")
    results = analyze_with_bedrock(tfplan_path)
    print(results)

    # Using multiple analyzers

    # Async analysis example
    async def async_analysis_example():
        llm = initialize_ollama_model()
        result = await analyze_risks_async(llm, tfplan_path)
        print("\nAsync analysis result:")
        print(result)

    asyncio.run(async_analysis_example())
