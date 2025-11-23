from datetime import datetime
from typing import Dict, Any, List, TypedDict

from agents.utils.agent_utils import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

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

# 입력된 사용자의 역할과 능력을 가져오는 툴
@tool
def get_users_job_and_skill_info(user_ids: List[int]) -> List[Dict[str, Any]]:
    """Get user's job and skill information. Returns list of user job and skill data."""
    
    # 더미 데이터 (실제로는 DB에서 가져올 데이터)
    dummy_users = {
        1: {"job": "po", "skills": ["product_strategy", "user_research", "backlog_management"]},
        2: {"job": "pm", "skills": ["project_management", "agile", "communication"]},
        3: {"job": "scrummaster", "skills": ["scrum", "facilitation", "team_coaching"]},
        4: {"job": "developer_frontend", "skills": ["react", "typescript", "css", "ux"]},
        5: {"job": "developer_backend", "skills": ["python", "fastapi", "postgresql", "redis"]},
        6: {"job": "designer", "skills": ["ui_design", "ux_design", "figma", "prototyping"]},
        7: {"job": "developer_ai", "skills": ["machine_learning", "pytorch", "nlp", "llm"]},
    }
    
    result = []
    for user_id in user_ids:
        if user_id in dummy_users:
            result.append({
                "user_id": user_id,
                "job": dummy_users[user_id]["job"],
                "skills": dummy_users[user_id]["skills"]
            })
        else:
            # 사용자가 없는 경우 기본값
            result.append({
                "user_id": user_id,
                "job": "unknown",
                "skills": []
            })
    
    return result

# 오늘 날짜를 가져오는 툴
@tool
def get_today_date() -> str:
    """Get today's date in YYYY-MM-DD format."""
    return datetime.now().strftime("%Y-%m-%d")

tools = [get_users_job_and_skill_info, get_today_date]

# ReAct 에이전트 생성
user_input_analyze_agent = create_agent(
    name="User input analyzer",
    model=llm,
    tools=tools,
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