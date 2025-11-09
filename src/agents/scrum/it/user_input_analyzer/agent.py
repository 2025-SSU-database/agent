from datetime import datetime
from typing import Dict, Any, List, TypedDict

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_mcp_adapters.client import MultiServerMCPClient  
from pydantic import BaseModel, Field

import os
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(model="gpt-4o")

# Output schema for parsed results
class TeamMember(BaseModel):
    user_id: int
    job: str
    skills: List[str]

class AnalysisOutput(BaseModel):
    project_name: str = Field(description="Name of the project or product")
    duration: str = Field(description="Sprint duration or timeline")
    team_members: List[TeamMember] = Field(description="Detailed information of team members")
    requirements: str = Field(description="Key requirements or constraints")

parser = JsonOutputParser(pydantic_object=AnalysisOutput)

# 오늘 날짜를 가져오는 툴
@tool
def get_today_date() -> str:
    """Get today's date in YYYY-MM-DD format."""
    return datetime.now().strftime("%Y-%m-%d")

tools = [get_today_date]

async def user_input_analyze_agent():
    client = MultiServerMCPClient({
        "zenior": {
            "transport": "streamable_http",
            "url": os.getenv("ZENIOR_MCP_SERVER_URL")
        }
    })

    mcp_tools = await client.get_tools()

    return create_agent(
        name="User input analyzer",
        model=llm,
        tools=[get_today_date, *mcp_tools],
        system_prompt=f"""
            You are an analyzer that extracts information from planning documents for scrum schedule creation.

            1. Get today's date using the get_today_date tool if the user mentions "today" or relative dates
            2. Extract team member IDs from the user input
            3. Use the get_users_job_and_skill_info tool to fetch detailed information about those team members
            4. Return the following information in a structured JSON format:
               - duration: sprint duration or timeline (start date, end date, or sprint length)
               - team_members: detailed information of team members (job, skills) - use the tool to get this
               - project_name: name of the project or product
               - requirements: key requirements or constraints

            Be concise and extract only the essential information provided.
        """
    )

