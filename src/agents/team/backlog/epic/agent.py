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

class Epic(BaseModel):
    title: str = Field(description="Title of the epic")
    description: str = Field(description="Detailed description of the epic")
    use_case_id: str = Field(description="ID or reference to the parent use case")
    priority: str = Field(description="Priority level (high, medium, low)")
    estimated_effort: int = Field(description="Estimated effort in story points")
    estimated_duration_weeks: int = Field(description="Estimated duration in weeks")
    order: int = Field(description="Order/sequence number of the epic (1, 2, 3, ...)")

class EpicOutput(BaseModel):
    use_case_title: str = Field(description="Title of the parent use case")
    epics: List[Epic] = Field(description="List of epics for this use case")

async def create_epic_agent(config: RunnableConfig):
    tools = []

    mcp_tools = await setup_mcp_tools(config)   

    if mcp_tools:
        tools.extend(mcp_tools)

    return create_agent(
        name="EpicAgent",
        model=llm,
        tools=tools,
        system_prompt=prompt,
        response_format=EpicOutput
    )
