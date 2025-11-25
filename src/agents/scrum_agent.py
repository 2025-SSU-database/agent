from typing import List, TypedDict, Annotated, Optional
import operator
from langchain.agents import create_agent
from langchain_core.messages import BaseMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.state import RunnableConfig
from pydantic import BaseModel

from .team import create_team_supervisor
from .mcp_utils import setup_mcp_tools
from .schema import Backlog, Sprint
from .team.common_tools import request_workspace_selection, request_project_selection

from dotenv import load_dotenv

load_dotenv()

from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()

MODEL_NAME = "gpt-5"

class ScrumState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    requirements: str

    # Backlog data
    backlog: Annotated[List[Backlog], operator.add]

    # Sprint data
    sprints: Annotated[List[Sprint], operator.add]

    # Project data
    project_report: dict

    # Supervisor routing
    next: str

    # User input collection
    needs_user_input: bool  # Whether user input is needed
    user_question: Optional[str]  # Question to ask user


prompt = """
You are a Scrum Master supervisor tasked with coordinating between the Backlog Team, Sprint Team, and Project Team. Analyze the user's request and decide which team should act next.

Your teams:
- BacklogAgent: Handles creating/modifying use cases, epics, user stories, and tasks
- SprintAgent: Handles sprint planning and sprint schedule adjustments
- ProjectAgent: Handles project planning, progress monitoring, resource allocation, risk management, and final reporting

IMPORTANT - Handling Information Requests:
- If ANY agent (BacklogAgent, SprintAgent, or ProjectAgent) requests additional information from the user (e.g., 프로젝트 기간, 팀 구성, 상세 기획 등), you MUST respond with FINISH.
- This allows the user to provide the missing information.
- Examples of missing info: 프로젝트 기간, 팀원 수/구성, 상세 기획, 기술 스택, 프로젝트 목표
- **Always ask questions and make requests in Korean.**

IMPORTANT - MCP Tool Usage Order:
- When using MCP tools, ALWAYS perform create (생성) and read (조회) operations FIRST.
- Save operations (update, save, delete, modify 등 - 생성과 조회를 제외한 모든 저장 작업) MUST be performed LAST, after all other work is completed.
- This ensures data integrity and allows for proper validation before saving.

IMPORTANT - Handling Missing IDs:
- If you need to create a project but don't have a workspace_id, use the `request_workspace_selection` tool.
- If you need to create a backlog or sprint but don't have a project_id, use the `request_project_selection` tool (you may need to ask for workspace_id first or infer it).

Analyze the conversation history to understand what has been done and what needs to be done next.
"""

def get_next_node(state: ScrumState) -> str:
    """Get the next node from supervisor's decision."""
    return state["next"]


async def create_backlog_agent(config: RunnableConfig):
    class BacklogOutput(BaseModel):
        backlog: List[Backlog]

    llm = ChatOpenAI(model=MODEL_NAME, use_responses_api=True)

    tools = [request_project_selection]

    mcp_tools = await setup_mcp_tools(config)

    if mcp_tools:
        tools.extend(mcp_tools)

    agent = create_agent(
        name="BacklogAgent",
        model=llm,
        tools=tools,
        system_prompt="""
            You are usefull agent for managing backlog. 

            IMPORTANT: 
                - When using MCP tools, always perform create and read operations first. 
                - Save operations (update, save, delete, modify - anything except create and read) must be performed LAST, after all other work is completed.
        """,
        interrupt_before=["tools"],
        response_format=BacklogOutput,
    )

    return agent

async def create_sprint_agent(config: RunnableConfig):
    class SprintOutput(BaseModel):
        sprint: Sprint

    llm = ChatOpenAI(model=MODEL_NAME, use_responses_api=True)

    tools = []

    mcp_tools = await setup_mcp_tools(config)

    if mcp_tools:
        tools.extend(mcp_tools)

    agent = create_agent(
        name="SprintAgent",
        model=llm,
        tools=tools,
        system_prompt="""
            You are usefull agent for managing sprint. 

            IMPORTANT: When using MCP tools, always perform create and read operations first. 
                - Save operations (update, save, delete, modify - anything except create and read) must be performed LAST, after all other work is completed.
        """,
        interrupt_before=["tools"],
        response_format=SprintOutput,
    )

    return agent

async def create_project_agent(config: RunnableConfig):
    llm = ChatOpenAI(model=MODEL_NAME, use_responses_api=True)
    tools = [request_workspace_selection]

    mcp_tools = await setup_mcp_tools(config)

    if mcp_tools:
        tools.extend(mcp_tools)

    agent = create_agent(
        name="ProjectAgent",
        model=llm,
        tools=tools,
        system_prompt="""
            You are usefull agent for managing project. 
            IMPORTANT: When using MCP tools, always perform create and read operations first. 
                - Save operations (update, save, delete, modify - anything except create and read) must be performed LAST, after all other work is completed.
        """,
        interrupt_before=["tools"],
    )

    return agent

async def create_scrum_agent_graph(config: Optional[RunnableConfig] = None):

    backlog_agent = await create_backlog_agent(config)
    sprint_agent = await create_sprint_agent(config)
    project_agent = await create_project_agent(config)
    
    members = ["BacklogAgent", "SprintAgent", "ProjectAgent"]

    supervisor_agent = await create_team_supervisor(
        "gpt-4o",
        prompt,
        members,
    )

    async def backlog_node(state: ScrumState, config: RunnableConfig):
        result = await backlog_agent.ainvoke(state)

        output = result.get("structured_response")

        if output:
            return {
                "backlog": output.backlog,
                "messages": result['messages'] + [AIMessage(content=f"BacklogAgent completed work.", name="BacklogAgent")]
            }
        else:
            return {
                "messages": result['messages']
            }


    async def sprint_node(state: ScrumState):
        result = await sprint_agent.ainvoke(state)

        output = result.get("structured_response")

        if output:
            return {
                "sprint": output.sprint,
                "messages": result['messages'] + [AIMessage(content=f"SprintAgent completed work.", name="SprintAgent")]
            }
        else:
            return {
                "messages": result['messages']
            }

    graph = StateGraph(ScrumState)
    
    graph.add_node("Supervisor", supervisor_agent)
    graph.add_node("BacklogAgent", backlog_node)
    graph.add_node("SprintAgent", sprint_node)
    graph.add_node("ProjectAgent", project_agent)
    
    graph.set_entry_point("Supervisor")
    
    graph.add_conditional_edges(
        "Supervisor",
        get_next_node,
        {
            "BacklogAgent": "BacklogAgent",
            "SprintAgent": "SprintAgent",
            "ProjectAgent": "ProjectAgent",
            "FINISH": END
        }
    )
    
    for member in members:
        graph.add_edge(member, "Supervisor")

    return graph.compile(checkpointer=checkpointer)
