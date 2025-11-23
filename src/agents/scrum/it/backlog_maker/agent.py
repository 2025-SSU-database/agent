from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from agents.utils.agent_utils import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field
from langgraph.types import interrupt
from langchain_core.runnables import RunnableConfig

from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(model="gpt-4o")

# Output schema for backlog items
class BacklogItem(BaseModel):
    title: str = Field(description="Title of the backlog item")
    description: str = Field(description="Detailed description of the backlog item")
    priority: str = Field(description="Priority level (high, medium, low)")
    estimated_effort: int = Field(description="Estimated effort in story points")
    estimated_duration_days: int = Field(description="Estimated duration in days to complete this item")
    assigned_to: str = Field(description="Job role or team member assigned to this item")
    order: int = Field(description="Order/sequence number of the backlog item (1, 2, 3, ...)")

class BacklogOutput(BaseModel):
    project_name: str = Field(description="Name of the project")
    items: List[BacklogItem] = Field(description="List of backlog items")

parser = JsonOutputParser(pydantic_object=BacklogOutput)

# Tool to generate backlog items from requirements
@tool
def generate_backlog_items(requirements: str, team_info: str) -> str:
    """Generate initial backlog items from requirements and team information."""
    # This would typically call an AI or logic to break down requirements
    return f"Generated backlog structure for: {requirements}"

# Tool to estimate effort for items
@tool
def estimate_effort(item_title: str, team_skills: List[str]) -> int:
    """Estimate effort in story points based on item complexity and team skills."""
    # Simple estimation logic (would be more sophisticated in production)
    base_effort = len(item_title.split())
    return max(1, min(13, base_effort * 2))

# Tool to estimate duration for items
@tool
def estimate_duration(story_points: int, team_size: int = 1) -> int:
    """Estimate duration in days based on story points and team size."""
    # 일반적인 기준: 1 스토리 포인트 = 0.5-1일 (팀원 1명 기준)
    # 팀원이 많을수록 병렬 작업 가능하므로 기간 단축
    base_days_per_point = 0.75
    estimated_days = int(story_points * base_days_per_point / team_size)
    return max(1, estimated_days)  # 최소 1일

@tool
def collect_more_data_from_user(question: str) -> str:
    """Collect more data from the user."""
    return interrupt(question)

tools = [generate_backlog_items, estimate_effort, estimate_duration]


def extract_json_from_message(message: AIMessage) -> Optional[dict]:
    """AI 메시지에서 JSON 추출"""
    if not isinstance(message, AIMessage):
        return None

    content = message.content
    if not isinstance(content, str):
        return None

    # JSON 코드 블록에서 추출
    if "```json" in content:
        start = content.find("```json") + 7
        end = content.find("```", start)
        json_str = content[start:end].strip()
    elif "```" in content:
        start = content.find("```") + 3
        end = content.find("```", start)
        json_str = content[start:end].strip()
    else:
        json_str = content.strip()

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


async def create_backlog_generator(config: RunnableConfig):
    """백로그 생성 에이전트 생성"""
    return create_agent(
        name="Backlog",
        model=llm,
        tools=[*tools, collect_more_data_from_user],
        system_prompt=f"""
            You are a backlog generation agent that creates structured backlog items from project requirements.

            1. Analyze the project requirements and team information provided
            2. Break down requirements into specific, actionable backlog items
            3. For each item, estimate effort using the estimate_effort tool
            4. Estimate duration using the estimate_duration tool based on story points and team size
            5. Assign items to appropriate team members based on their skills
            6. Return the following information in a structured JSON format:
               - project_name: name of the project
               - items: list of backlog items with title, description, priority, estimated_effort, estimated_duration_days, assigned_to, and order

            Guidelines:
            - Create clear, testable user stories or tasks
            - Prioritize items based on dependencies and business value
            - Distribute work across team members appropriately
            - Be specific and actionable in item descriptions
            - Duration should be estimated in days based on story points and available team members
            - Consider that multiple team members can work in parallel to reduce duration
            - IMPORTANT: Assign a sequential order number (1, 2, 3, ...) to each backlog item based on priority and dependencies. This order will be used to maintain sequence in sprints
            - If any required information is missing or unclear, use the collect_more_data_from_user tool to ask clarifying questions
            - Ask specific, concise questions one at a time when needed

            Return the following information in a structured JSON format:
        """,
        response_format=BacklogOutput
    )