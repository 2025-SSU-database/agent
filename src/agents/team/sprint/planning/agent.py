from typing import List, Optional, Any      
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .prompt import prompt

load_dotenv()

llm = ChatOpenAI(model="gpt-4o", temperature=0)

class Sprint(BaseModel):
    sprint_number: int = Field(description="Sprint number (1, 2, ...)")
    goal: str = Field(description="Main goal of the sprint")
    start_date: str = Field(description="Start date of the sprint (YYYY-MM-DD)")
    end_date: str = Field(description="End date of the sprint (YYYY-MM-DD)")
    included_tasks: List[str] = Field(description="List of task titles included in this sprint")
    
class SprintOutput(BaseModel):
    project_name: str = Field(description="Name of the project")
    sprints: List[Sprint] = Field(description="List of planned sprints")

async def create_sprint_planning_agent(config: RunnableConfig, tools: Optional[List[Any]] = None):
    return create_agent(
        name="SprintPlanningAgent",
        model=llm,
        tools=tools or [],
        system_prompt=prompt,
        response_format=SprintOutput,
    )
