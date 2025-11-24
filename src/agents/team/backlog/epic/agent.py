from typing import List, Optional, Any
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os

from ....mcp_utils import setup_mcp_tools

from .prompt import prompt

load_dotenv()

llm = ChatOpenAI(model="gpt-4o", temperature=0)

class EpicOutput(BaseModel):
    use_case_title: str = Field(description="Title of the parent use case")
    epics: List[str] = Field(description="List of epics (Backlog items) for this use case")

async def create_epic_agent(config: RunnableConfig):
    tools = []
    
    token = config.get("configurable", {}).get("token") if config else None
    if not token:
        raise ValueError("Token is required")

    mcp_list = {
        "backlog": {
            "transport": "streamable_http",
            "url": os.getenv("ZENIOR_MCP_SERVER_URL"),
            "headers": {
                "Authorization": f"Bearer {token}"
            }
        }
    }
    mcp_tools = await setup_mcp_tools(config, mcp_list)

    if mcp_tools:
        tools.extend(mcp_tools)

    return create_agent(
        name="EpicAgent",
        model=llm,
        tools=tools,
        system_prompt=prompt,
        response_format=EpicOutput,
        interrupt_before=["tools"]
    )
