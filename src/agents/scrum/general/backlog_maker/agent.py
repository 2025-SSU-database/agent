from typing import Dict, Any, List
from datetime import datetime

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(model="gpt-4o")

# Output schema for backlog items
class BacklogItem(BaseModel):
    title: str = Field(description="Title of the backlog item")
    description: str = Field(description="Detailed description of the backlog item")
    priority: str = Field(description="Priority level (high, medium, low)")
    estimated_effort: int = Field(description="Estimated effort in story points")
    assigned_to: str = Field(description="Job role or team member assigned to this item")

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

tools = [generate_backlog_items, estimate_effort]


backlog_agent = create_agent(
    name="Backlog",
    model=llm,
    tools=tools,
    system_prompt=f"""
        You are a backlog generation agent that creates structured backlog items from project requirements.

        1. Analyze the project requirements and team information provided
        2. Break down requirements into specific, actionable backlog items
        3. For each item, estimate effort using the estimate_effort tool
        4. Assign items to appropriate team members based on their skills
        5. Return the following information in a structured JSON format:
           - project_name: name of the project
           - items: list of backlog items with title, description, priority, estimated_effort, and assigned_to

        Guidelines:
        - Create clear, testable user stories or tasks
        - Prioritize items based on dependencies and business value
        - Distribute work across team members appropriately
        - Be specific and actionable in item descriptions

        {parser.get_format_instructions()}
    """
)