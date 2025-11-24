from typing import List, Optional, Any
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from dotenv import load_dotenv

from .prompt import prompt

load_dotenv()

llm = ChatOpenAI(model="gpt-4o", temperature=0)

class UseCase(BaseModel):
    title: str = Field(description="Title of the use case")
    description: str = Field(description="Description of the use case")
    business_value: str = Field(description="Business value of the use case")
    priority: int = Field(description="Priority of the use case")
    estimated_effort: int = Field(description="Estimated effort to complete the use case")
    estimated_duration: int = Field(description="Estimated duration to complete the use case")
    assignee: str = Field(description="Assignee of the use case")

class UseCaseOutput(BaseModel):
    project_name: str = Field(description="Name of the project")
    use_cases: List[UseCase] = Field(description="List of use cases for this project")

async def create_use_case_agent(config: RunnableConfig):
    return create_agent(
        name="UseCaseAgent",
        model=llm,
        system_prompt=prompt,
        response_format=UseCaseOutput,
    )
