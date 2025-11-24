import json
from typing import List, TypedDict, Annotated, Optional
import operator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.state import RunnableConfig

from .team import create_backlog_team_graph, create_sprint_team_graph, create_project_team_graph, create_team_supervisor

from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()

MODEL_NAME = "gpt-4o"

class ScrumState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    requirements: str
    # Backlog data
    use_cases: Annotated[List[dict], operator.add]
    epics: Annotated[List[dict], operator.add]
    user_stories: Annotated[List[dict], operator.add]
    tasks: Annotated[List[dict], operator.add]

    # Sprint data
    sprints: Annotated[List[dict], operator.add]

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
- BacklogTeam: Handles creating/modifying use cases, epics, user stories, and tasks
- SprintTeam: Handles sprint planning and sprint schedule adjustments
- ProjectTeam: Handles project planning, progress monitoring, resource allocation, risk management, and final reporting

IMPORTANT - Handling Information Requests:
- If ANY sub-graph (BacklogTeam, SprintTeam, or ProjectTeam) requests additional information from the user (e.g., 프로젝트 기간, 팀 구성, 상세 기획 등), you MUST respond with FINISH.
- This allows the user to provide the missing information.
- Examples of missing info: 프로젝트 기간, 팀원 수/구성, 상세 기획, 기술 스택, 프로젝트 목표
- **Always ask questions and make requests in Korean.**

Analyze the conversation history to understand what has been done and what needs to be done next.
"""

def get_next_node(state: ScrumState) -> str:
    """Get the next node from supervisor's decision."""
    return state["next"]


async def create_scrum_agent_graph(config: Optional[RunnableConfig] = None):
    backlog_team = await create_backlog_team_graph(config)
    sprint_team = await create_sprint_team_graph(config)
    project_team = await create_project_team_graph(config)
    
    members = ["BacklogTeam", "SprintTeam", "ProjectTeam"]

    supervisor_agent = await create_team_supervisor(
        MODEL_NAME,
        prompt,
        members,
    )

    async def backlog_node(state: ScrumState):
        """Backlog team node - handles backlog generation."""

        messages = state.get("messages", [])
        
        if state.get("requirements"):
            msg = f"Project Requirements:\n{state['requirements']}"

        else:
            user_messages = [m for m in messages if isinstance(m, HumanMessage)]
            msg = user_messages[-1].content if user_messages else "Generate backlog items"
        
        response = await backlog_team.ainvoke({"messages": [HumanMessage(content=msg)]})
        
        use_cases = response.get("use_cases", [])
        epics = response.get("epics", [])
        user_stories = response.get("user_stories", [])
        tasks = response.get("tasks", [])
        
        summary = f"BacklogTeam completed work.\nGenerated:\n- {len(use_cases)} Use Cases\n- {len(epics)} Epics\n- {len(user_stories)} User Stories\n- {len(tasks)} Tasks"
        
        return {
            "use_cases": use_cases,
            "epics": epics,
            "user_stories": user_stories,
            "tasks": tasks,
            "messages": [AIMessage(content=summary, name="BacklogTeam")]
        }

    async def sprint_node(state: ScrumState):
        tasks = state.get("tasks", [])
        # Pass existing sprints if any, though usually we generate new ones
        response = await sprint_team.ainvoke({"tasks": tasks, "messages": state.get("messages", [])})
        
        return {
            "sprints": response.get("sprints", []),
            "messages": [AIMessage(content="SprintTeam completed work.", name="SprintTeam")]
        }

    async def project_node(state: ScrumState):
        sprints = state.get("sprints", [])
        tasks = state.get("tasks", [])
        
        response = await project_team.ainvoke({"sprints": sprints, "tasks": tasks})
        
        # We might want to persist the report in state
        report = response.get("project_report", {})
        
        return {
            "project_report": report,
            "messages": [AIMessage(content="ProjectTeam completed work.", name="ProjectTeam")]
        }

    graph = StateGraph(ScrumState)
    
    graph.add_node("Supervisor", supervisor_agent)
    graph.add_node("BacklogTeam", backlog_node)
    graph.add_node("SprintTeam", sprint_node)
    graph.add_node("ProjectTeam", project_node)
    
    graph.set_entry_point("Supervisor")
    
    graph.add_conditional_edges(
        "Supervisor",
        get_next_node,
        {
            "BacklogTeam": "BacklogTeam",
            "SprintTeam": "SprintTeam",
            "ProjectTeam": "ProjectTeam",
            "FINISH": END
        }
    )
    
    for member in members:
        graph.add_edge(member, "Supervisor")

    return graph.compile(checkpointer=checkpointer)
