from typing import List, Optional, Any
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from dotenv import load_dotenv

from agents.mcp_utils import setup_mcp_tools

from .prompt import prompt

load_dotenv()

llm = ChatOpenAI(model="gpt-4o", temperature=0)

class UseCase(BaseModel):
    title: str = Field(description="Title of the use case")
    description: str = Field(description="Detailed description of the use case")
    business_value: str = Field(description="Business value or goal this use case addresses")
    priority: str = Field(description="Priority level (high, medium, low)")
    order: int = Field(description="Order/sequence number of the use case (1, 2, 3, ...)")

class UseCaseOutput(BaseModel):
    project_name: str = Field(description="Name of the project")
    use_cases: List[UseCase] = Field(description="List of use cases")

async def create_use_case_agent(config: RunnableConfig):
    tools = []

    mcp_tools = await setup_mcp_tools(config)   

    if mcp_tools:
        tools.extend(mcp_tools)

    return create_agent(
        name="UseCaseAgent",
        model=llm,
        tools=tools,
        system_prompt=prompt,
        response_format=UseCaseOutput
    )
