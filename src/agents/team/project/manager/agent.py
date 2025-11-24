
from typing import List, Optional, Any, Dict, Tuple
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os

from ....mcp_utils import setup_mcp_tools

from .prompt import prompt

load_dotenv()

llm = ChatOpenAI(model="gpt-4o", temperature=0)

class Risk(BaseModel):
    risk_description: str = Field(description="Description of the risk")
    severity: str = Field(description="Severity (High, Medium, Low)")
    mitigation: str = Field(description="Suggested mitigation strategy")

class ResourceRecommendation(BaseModel):
    role: str = Field(description="Role needed or affected (e.g. Frontend Dev)")
    recommendation: str = Field(description="Advice on allocation or hiring")

class ProjectStatusReport(BaseModel):
    overall_status: str = Field(description="Overall project status (On Track, At Risk, Delayed)")
    completion_percentage_estimate: float = Field(description="Estimated completion percentage based on tasks planned vs total")
    summary: str = Field(description="Executive summary of the project status")
    risks: List[Risk] = Field(description="Identified risks")
    resource_recommendations: List[ResourceRecommendation] = Field(description="Resource allocation advice")
    next_steps: List[str] = Field(description="Actionable next steps for the team")

async def create_project_manager_agent(config: RunnableConfig) -> Tuple[Any, List[Any]]:

    token = config.get("configurable", {}).get("token") if config else None
    if not token:
        raise ValueError("Token is required")

    tools = []

    mcp_list = {
        "project": {
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
        name="ProjectManagerAgent",
        model=llm,
        tools=tools,
        system_prompt=prompt,
        response_format=ProjectStatusReport,
        interrupt_before=["tools"] 
    )       
