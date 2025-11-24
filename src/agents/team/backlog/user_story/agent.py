from typing import List, Optional, Any
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from .prompt import prompt

llm = ChatOpenAI(model="gpt-4o", temperature=0)

class UserStoryOutput(BaseModel):
    epic_title: str = Field(description="Title of the parent epic")
    user_stories: List[str] = Field(description="List of user stories (Backlog items) for this epic")

async def create_user_story_agent(config: RunnableConfig):
    """유저 스토리 생성 에이전트"""
    return create_agent(
        name="UserStoryAgent",
        model=llm,
        system_prompt=prompt,
        response_format=UserStoryOutput
    )
