from datetime import datetime
from typing import List

from agents.utils.agent_utils import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph.state import RunnableConfig
from pydantic import BaseModel, Field
from langgraph.types import interrupt
from dotenv import load_dotenv

import os

load_dotenv()

class TeamMember(BaseModel):
    user_id: int
    job: str
    skills: List[str]

class AnalysisOutput(BaseModel):
    project_name: str = Field(description="Name of the project or product")
    duration: str = Field(
        description="Project duration in format 'YYYY-MM-DD to YYYY-MM-DD' or 'YYYY-MM-DD ~ YYYY-MM-DD'. "
        "MUST include both start date and end date in YYYY-MM-DD format. "
        "Examples: '2025-11-16 to 2025-12-07', '2025-01-01 ~ 2025-03-31'. "
        "DO NOT use only year (e.g., '2025') or incomplete dates. "
        "If user mentions relative dates like '3 months from today', calculate actual dates using get_today_date tool."
    )
    team_members: List[TeamMember] = Field(description="Detailed information of team members")
    requirements: str = Field(description="Key requirements or constraints")

llm = ChatOpenAI(model="gpt-4o-mini")

@tool
def get_today_date() -> str:
    """Get today's date in YYYY-MM-DD format."""
    return datetime.now().strftime("%Y-%m-%d")

async def create_user_input_analyzer(config: RunnableConfig):
    """사용자 입력 분석 에이전트 생성"""
    mcp_url = os.getenv("ZENIOR_MCP_SERVER_URL")

    token = config.get("configurable", {}).get("token")

    if not mcp_url:
        if not token:
            raise ValueError("Token is required")
        else:
            print("⚠️  경고: ZENIOR_MCP_SERVER_URL 환경 변수가 설정되지 않았습니다. MCP 도구 없이 실행합니다.")
        mcp_tools = []
    else:
        try:
            client = MultiServerMCPClient({
                "zenior": {
                    "transport": "streamable_http",
                    "url": mcp_url,
                    "headers": {
                        "Authorization": f"Bearer {token}"
                    }
                }
            })
            mcp_tools = await client.get_tools()
        except Exception as e:
            import traceback
            traceback.print_exc()
            mcp_tools = []

    if mcp_tools:
        team_member_instruction = "3. Use the get_users_job_and_skill_info tool to fetch detailed information about those team members"
    else:
        team_member_instruction = "3. Extract team member information from the user input directly (job and skills if mentioned)"

    return create_agent(
        name="User input analyzer",
        model=llm,
        tools=[get_today_date, *mcp_tools],
        system_prompt=f"""
            You are an intelligent analyzer that extracts information from planning documents for scrum schedule creation.
            Your role is to gather complete and accurate information from users through conversation.

            INSTRUCTIONS:
            1. Get today's date using the get_today_date tool if the user mentions "today" or relative dates
            2. Extract team member IDs from the user input
            {team_member_instruction}
            4. If any required information is missing or unclear, use the collect_more_data_from_user tool to ask clarifying questions
            5. Extract only the essential information needed and structure it in JSON format

            REQUIRED INFORMATION TO COLLECT:
            - duration: Project duration MUST be in format 'YYYY-MM-DD to YYYY-MM-DD' or 'YYYY-MM-DD ~ YYYY-MM-DD'
              * MUST include both start date and end date in full YYYY-MM-DD format
              * Examples: '2025-11-16 to 2025-12-07', '2025-01-01 ~ 2025-03-31'
              * DO NOT use only year (e.g., '2025') or incomplete dates
              * If user mentions relative dates (e.g., '3 months', 'next month'), use get_today_date tool and calculate actual dates
              * If user mentions only duration (e.g., '3 months'), calculate end date from start date
            - team_members: detailed information of team members (user_id, job, skills)
            - project_name: name of the project or product
            - requirements: key requirements or constraints

            IMPORTANT GUIDELINES:
            - Always ask for missing information using collect_more_data_from_user tool before responding
            - Ask specific, concise questions one at a time
            - Confirm extracted information with the user if uncertain
            - Be conversational and helpful while gathering information
            - Once you have all required information, respond with a structured JSON format
            - CRITICAL: For duration field, ALWAYS extract or calculate complete dates in YYYY-MM-DD format
              * If user says "2025", ask for specific start and end dates
              * If user says "3 months", use get_today_date tool and calculate: start_date = today, end_date = today + 3 months
              * NEVER return incomplete dates like "2025" or "2025-11" - always use full YYYY-MM-DD format

            Be proactive in asking follow-up questions to ensure you have complete information for sprint planning.
            
            Return the following information in a structured JSON format:
        """,
        response_format=AnalysisOutput
    )