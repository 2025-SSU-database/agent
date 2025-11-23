from typing import List, Optional, Any
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from agents.mcp_utils import setup_mcp_tools

from .prompt import prompt

load_dotenv()

llm = ChatOpenAI(model="gpt-4o", temperature=0)

class Task(BaseModel):
    title: str = Field(description="Title of the task")
    description: str = Field(description="Detailed description of the task")
    user_story_id: str = Field(description="ID or reference to the parent user story")
    priority: str = Field(description="Priority level (high, medium, low)")
    estimated_effort_hours: int = Field(description="Estimated effort in hours")
    assigned_to: str = Field(description="Job role or team member assigned to this task")
    order: int = Field(description="Order/sequence number of the task (1, 2, 3, ...)")

class TaskOutput(BaseModel):
    user_story_title: str = Field(description="Title of the parent user story")
    tasks: List[Task] = Field(description="List of tasks for this user story")

async def create_task_agent(config: RunnableConfig):
    tools = []

    mcp_tools = await setup_mcp_tools(config)   

    if mcp_tools:
        tools.extend(mcp_tools)

    return create_agent(
        name="TaskAgent",
        model=llm,
        tools=tools,
        system_prompt=prompt,
        response_format=TaskOutput
    )
