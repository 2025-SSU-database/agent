import operator
import json
import os
import re
from typing import TypedDict, Optional
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage
from langgraph.graph.state import RunnableConfig
from typing_extensions import Annotated
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient

from dotenv import load_dotenv

from .user_input_analyzer import create_user_input_analyzer
from .backlog_maker import create_backlog_generator
from .sprints_maker import create_sprint_planner    
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

load_dotenv()

class State(TypedDict, total=False):

    messages: Annotated[list[AnyMessage], operator.add]

    project_name: Optional[str]
    duration: Optional[str]
    team_members: Optional[list[dict]]
    requirements: Optional[str]

    backlog: Optional[list[dict]]
    sprints: Optional[list[dict]]
    workspace_id: Optional[str]  # Workspace ID for project creation



async def create_supervisor():
    # 그래프 생성
    graph_builder = StateGraph(State)


    return graph_builder.compile()
