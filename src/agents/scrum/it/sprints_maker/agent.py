from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
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

# Output schema for sprint backlog item reference
class SprintBacklogItem(BaseModel):
    title: str = Field(description="Title of the backlog item")
    order: int = Field(description="Order/sequence of this item within the sprint (1, 2, 3, ...)")

# Output schema for sprint items
class SprintItem(BaseModel):
    sprint_number: int = Field(description="Sprint number (1, 2, 3, ...)")
    sprint_name: str = Field(description="Name of the sprint")
    start_date: str = Field(description="Start date in YYYY-MM-DD format")
    end_date: str = Field(description="End date in YYYY-MM-DD format")
    goal: str = Field(description="Sprint goal or objective")
    backlog_items: List[SprintBacklogItem] = Field(description="List of backlog items included in this sprint with their order")
    team_capacity: int = Field(description="Total team capacity in story points for this sprint")

class SprintsOutput(BaseModel):
    project_name: str = Field(description="Name of the project")
    sprint_duration_weeks: int = Field(description="Duration of each sprint in weeks")
    sprints: List[SprintItem] = Field(description="List of sprints")

# Tool to calculate sprint dates
@tool
def calculate_sprint_dates(start_date: str, sprint_number: int, sprint_duration_weeks: int) -> Dict[str, str]:
    """Calculate start and end dates for a sprint based on project start date and sprint number."""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        sprint_start = start + timedelta(weeks=(sprint_number - 1) * sprint_duration_weeks)
        sprint_end = sprint_start + timedelta(weeks=sprint_duration_weeks) - timedelta(days=1)
        return {
            "start_date": sprint_start.strftime("%Y-%m-%d"),
            "end_date": sprint_end.strftime("%Y-%m-%d")
        }
    except Exception as e:
        return {"error": str(e)}

# Tool to estimate team capacity
@tool
def estimate_team_capacity(team_size: int, sprint_duration_weeks: int) -> int:
    """Estimate team capacity in story points based on team size and sprint duration."""
    # 일반적인 기준: 1인당 주당 5-8 스토리 포인트
    points_per_person_per_week = 6
    return team_size * sprint_duration_weeks * points_per_person_per_week

# Tool to distribute backlog items across sprints
@tool
def distribute_backlog_items(backlog_items: List[Dict], team_capacity: int) -> List[List[Dict]]:
    """Distribute backlog items across sprints based on capacity and priority. Returns items with order information."""
    # 간단한 분배 로직: 우선순위와 스토리 포인트를 고려하여 분배
    distributed = []
    current_sprint = []
    current_capacity = 0
    sprint_order = 1
    
    # 우선순위와 원래 순서를 고려하여 정렬 (high > medium > low, 같은 우선순위면 원래 순서 유지)
    priority_order = {"high": 3, "medium": 2, "low": 1}
    sorted_items = sorted(
        backlog_items,
        key=lambda x: (
            priority_order.get(x.get("priority", "medium"), 2),
            -x.get("order", 0),  # 원래 순서 고려 (높은 순서가 먼저)
            -x.get("estimated_effort", 0)
        ),
        reverse=True
    )
    
    for item in sorted_items:
        effort = item.get("estimated_effort", 0)
        if current_capacity + effort <= team_capacity:
            # 순서 정보와 함께 저장
            current_sprint.append({
                "title": item.get("title", ""),
                "order": sprint_order,
                "original_order": item.get("order", 0)
            })
            sprint_order += 1
            current_capacity += effort
        else:
            if current_sprint:
                distributed.append(current_sprint)
            sprint_order = 1
            current_sprint = [{
                "title": item.get("title", ""),
                "order": sprint_order,
                "original_order": item.get("order", 0)
            }]
            sprint_order += 1
            current_capacity = effort
    
    if current_sprint:
        distributed.append(current_sprint)
    
    return distributed

@tool
def collect_more_data_from_user(question: str) -> str:
    """Collect more data from the user."""
    return interrupt(question)

tools = [calculate_sprint_dates, estimate_team_capacity, distribute_backlog_items]

async def create_sprint_planner(config: RunnableConfig):
    """스프린트 계획 에이전트 생성"""
    return create_agent(
        name="Sprints",
        model=llm,
        tools=[*tools, collect_more_data_from_user],
        system_prompt=f"""
            You are a sprint planning agent that creates structured sprint plans from backlog items and project timeline.

            1. Analyze the project duration, backlog items, and team information provided
            2. Determine appropriate sprint duration (typically 1-4 weeks)
            3. Calculate sprint dates using the calculate_sprint_dates tool
            4. Estimate team capacity using the estimate_team_capacity tool
            5. Distribute backlog items across sprints using the distribute_backlog_items tool
            6. Create sprint goals based on the items in each sprint
            7. Return the following information in a structured JSON format:
               - project_name: name of the project
               - sprint_duration_weeks: duration of each sprint in weeks
               - sprints: list of sprints with sprint_number, sprint_name, start_date, end_date, goal, backlog_items, and team_capacity

            Guidelines:
            - Sprint duration should be consistent (typically 2 weeks)
            - Distribute backlog items based on priority and dependencies
            - Ensure each sprint has a clear, achievable goal
            - Don't exceed team capacity in any sprint
            - Consider dependencies between backlog items
            - Sprint names should be descriptive (e.g., "Sprint 1: Foundation", "Sprint 2: Core Features")
            - IMPORTANT: Maintain the order of backlog items within each sprint. Each backlog item in the sprint should have an "order" field (1, 2, 3, ...) indicating its sequence within that sprint
            - When creating backlog_items in sprints, use the SprintBacklogItem format with both "title" and "order" fields
            - If any required information is missing or unclear, use the collect_more_data_from_user tool to ask clarifying questions
            - Ask specific, concise questions one at a time when needed
        """,
        response_format=SprintsOutput
    )