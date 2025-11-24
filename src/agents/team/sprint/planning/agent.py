from typing import List, Optional, Any      
from ....mcp_utils import setup_mcp_tools
from ....schema import Sprint
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os

from .prompt import prompt

load_dotenv()

llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
class SprintOutput(BaseModel):
    project_name: str = Field(description="Name of the project")
    sprints: List[Sprint] = Field(description="List of planned sprints")

async def create_sprint_planning_agent(config: RunnableConfig, tools: Optional[List[Any]] = None):
    token = config.get("configurable", {}).get("token") if config else None
    
    if not token:
        raise ValueError("Token is required")

    mcp_list = {
        "sprint": {
            "transport": "streamable_http",
            "url": os.getenv("ZENIOR_MCP_SERVER_URL"),
            "headers": {
                "Authorization": f"Bearer {token}"
            }
        }
    }

    _tools = []

    mcp_tools = await setup_mcp_tools(config, mcp_list)

    if mcp_tools:
        _tools.extend(mcp_tools)

    if tools:
        _tools.extend(tools)

    agent = create_agent(
        name="SprintPlanningAgent",
        model=llm,
        tools=_tools,
        system_prompt=prompt,
        interrupt_before=["tools"],
        response_format=SprintOutput,
    )

    return agent