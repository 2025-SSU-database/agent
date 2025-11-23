from typing import List
from langchain.tools import tool

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
    """Request more information from the user. When you need additional information, use this tool to ask the user a question. The graph will end and wait for the user's response."""
    return f"[NEEDS_USER_INPUT] {question}"