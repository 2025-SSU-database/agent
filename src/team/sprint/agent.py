from enum import Enum
from typing import List, Optional
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph.state import RunnableConfig
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from ..hand_off_agent import create_interactive_agent
from ..mcp_utils import setup_mcp_tools
from .prompt import prompt

class SprintStatus(str, Enum):
  PLANNED = "PLANNED"
  ACTIVE = "ACTIVE"
  COMPLETED = "COMPLETED"
  ABORTED = "ABORTED"

class Sprint(BaseModel):
  """
    Schema for Sprint entity, matching the Service (Core) Schema.
  """
  name: str = Field(description="Name of the sprint")
  sprint_number: int = Field(description="Sprint number")
  goal: Optional[str] = Field(description="Sprint goal")
  start_date: str = Field(description="Start date (YYYY-MM-DD)")
  end_date: str = Field(description="End date (YYYY-MM-DD)")
  status: SprintStatus = Field(default=SprintStatus.PLANNED, description="Status of the sprint")
  backlog_ids: Optional[List[str]] = Field(default=None, description="List of backlog IDs or titles included in the sprint")

class SprintOutput(BaseModel):
    sprints: Sprint

async def create_sprint_agent(config: RunnableConfig):
    llm = ChatOpenAI(
        model="gpt-4o", 
        use_responses_api=True,
        timeout=120,
        max_retries=3,
        request_timeout=120,
        name="SprintAgent",
    )

    tools = []

    mcp_tools = await setup_mcp_tools(config)

    agent = create_agent(
        model="gpt-4o",
        system_prompt=prompt,
        tools=[*tools, *mcp_tools],
        response_format=SprintOutput,
    )

    return agent