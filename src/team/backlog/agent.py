from enum import Enum
from typing import List, Optional
from langchain.agents import create_agent, structured_output
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph.state import RunnableConfig
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from ..hand_off_agent import create_interactive_agent
from .prompt import prompt
from ..mcp_utils import setup_mcp_tools

class BacklogStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    DONE = "DONE"
    ARCHIVED = "ARCHIVED"

class Backlog(BaseModel):
    """
    Schema for Backlog entity, matching the Service (Core) Schema.
    """
    title: str = Field(description="Title of the backlog item")
    description: str = Field(description="Detailed description")
    priority: Optional[int] = Field(description="Priority level (e.g., 1-5)")
    start_date: Optional[str] = Field(description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(description="End date (YYYY-MM-DD)")
    status: BacklogStatus = Field(default=BacklogStatus.TODO, description="Status of the backlog item")

class BacklogOutput(BaseModel):
    backlogs: List[Backlog]

@tool
def request_project_selection(workspace_id: str) -> dict:
    """
    Request the user to select a project within a specific workspace.
    Use this tool when you need a project_id to proceed (e.g., for creating a backlog) but one was not provided or is ambiguous.
    """
    
    project_id = interrupt("select project_id")

    return project_id

async def create_backlog_agent(config: RunnableConfig):


    # 타임아웃 및 재시도 설정 추가
    llm = ChatOpenAI(
        model="gpt-4o", 
        use_responses_api=True,
        timeout=120,
        max_retries=3,
        request_timeout=120,
        name="BacklogAgent",
    )

    tools = [request_project_selection]

    mcp_tools = await setup_mcp_tools(config)

    agent = create_agent(
        model="gpt-4o",
        system_prompt=prompt,
        tools=[*tools, *mcp_tools],
        response_format=BacklogOutput,
    )

    return agent