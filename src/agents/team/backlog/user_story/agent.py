from typing import List, Optional, Any
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from .prompt import prompt

llm = ChatOpenAI(model="gpt-4o", temperature=0)

class UserStory(BaseModel):
    title: str = Field(description="Title of the user story")
    description: str = Field(description="Detailed description following 'As a [user], I want [goal] so that [benefit]' format")
    acceptance_criteria: List[str] = Field(description="List of acceptance criteria")
    epic_id: str = Field(description="ID or reference to the parent epic")
    priority: str = Field(description="Priority level (high, medium, low)")
    estimated_effort: int = Field(description="Estimated effort in story points")
    estimated_duration_days: int = Field(description="Estimated duration in days")
    assigned_to: str = Field(description="Job role or team member assigned to this story")
    order: int = Field(description="Order/sequence number of the user story (1, 2, 3, ...)")

class UserStoryOutput(BaseModel):
    epic_title: str = Field(description="Title of the parent epic")
    user_stories: List[UserStory] = Field(description="List of user stories for this epic")

async def create_user_story_agent(config: RunnableConfig):
    """유저 스토리 생성 에이전트"""
    return create_agent(
        name="UserStoryAgent",
        model=llm,
        system_prompt=prompt,
        response_format=UserStoryOutput
    )
