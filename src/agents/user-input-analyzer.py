import json
from typing import Dict, Any, List

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(model="gpt-4o")

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant. Answer in Korean.",
        ),
        ("human", "{messages}"),
    ]
)

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

tools = [get_users_job_and_skill_info]

# ReAct 에이전트 생성
agent_executor = create_agent(llm, tools=tools)