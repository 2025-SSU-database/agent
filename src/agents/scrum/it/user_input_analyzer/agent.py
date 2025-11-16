from datetime import datetime
from typing import Annotated, Dict, Any, List, TypedDict, Optional
import json

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.messages import AIMessage, HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import add_messages
from pydantic import BaseModel, Field
from langgraph.types import interrupt

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

@tool
def collect_more_data_from_user(question: str) -> str:
    """Collect more data from the user."""
    return interrupt(question)

tools = [get_today_date]

async def create_user_input_analyzer():
    """사용자 입력 분석 에이전트 생성"""
    mcp_url = os.getenv("ZENIOR_MCP_SERVER_URL")

    # MCP 서버 URL이 설정되지 않은 경우 기본 도구만 사용
    if not mcp_url:
        print("⚠️  경고: ZENIOR_MCP_SERVER_URL 환경 변수가 설정되지 않았습니다. MCP 도구 없이 실행합니다.")
        mcp_tools = []
    else:
        try:
            client = MultiServerMCPClient({
                "zenior": {
                    "transport": "streamable_http",
                    "url": mcp_url
                }
            })
            mcp_tools = await client.get_tools()
        except Exception as e:
            print(f"⚠️  경고: MCP 서버 연결 실패 ({e}). MCP 도구 없이 실행합니다.")
            mcp_tools = []

    # MCP 도구가 있는 경우와 없는 경우에 따라 프롬프트 조정
    if mcp_tools:
        team_member_instruction = "3. Use the get_users_job_and_skill_info tool to fetch detailed information about those team members"
    else:
        team_member_instruction = "3. Extract team member information from the user input directly (job and skills if mentioned)"

    return create_agent(
        name="User input analyzer",
        model=llm,
        tools=[get_today_date, collect_more_data_from_user, *mcp_tools],
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
            - duration: sprint duration or timeline (start date, end date, or sprint length)
            - team_members: detailed information of team members (user_id, job, skills)
            - project_name: name of the project or product
            - requirements: key requirements or constraints

            IMPORTANT GUIDELINES:
            - Always ask for missing information using collect_more_data_from_user tool before responding
            - Ask specific, concise questions one at a time
            - Confirm extracted information with the user if uncertain
            - Be conversational and helpful while gathering information
            - Once you have all required information, respond with a structured JSON format

            Be proactive in asking follow-up questions to ensure you have complete information for sprint planning.
        """
    )

