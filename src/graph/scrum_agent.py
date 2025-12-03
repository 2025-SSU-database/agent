from functools import partial
from typing import List, TypedDict, Annotated, Optional
import operator
from typing_extensions import Any, Dict, Literal
from langchain_core.messages import BaseMessage, AIMessage
from langgraph.graph import START, StateGraph, END, add_messages
from langgraph.graph.state import RunnableConfig

from dotenv import load_dotenv

from .create_supervisor import create_team_supervisor
from .supervisor_prompt import prompt

from team.backlog import create_backlog_agent, Backlog
from team.sprint import create_sprint_agent, Sprint
from team.project import create_project_agent

load_dotenv()

from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()

MODEL_NAME = "gpt-4o"

class ScrumState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    requirements: str

    backlogs: Annotated[List[Backlog], operator.add]
    sprints: Annotated[List[Sprint], operator.add]
    project_report: dict

    next: str

def get_next_node(state: ScrumState) -> str:
    """Get the next node from supervisor's decision."""
    return state["next"]

def check_worker_handoff(state: ScrumState) -> Literal[END, "done"]:
    """
        마지막 메시지가 AI의 툴 호출이라면 'continue'를 반환하여 
        해당 에이전트가 다시 실행(결과 대기)되도록 합니다.
        그렇지 않다면 'done'을 반환하여 Supervisor에게 턴을 넘깁니다.
    """
    messages = state["messages"]
    if not messages:
        return "done"
        
    last_message = messages[-1]
    
    # AI가 툴을 호출한 상태라면 -> 자기 자신에게 돌아감 (Frontend Tool 대기 등)
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return END
        
    return "done"

async def run_agent_node(state: ScrumState, agent: Any, name: str) -> Dict[str, Any]:
    original_count = len(state["messages"])
    
    result = await agent.ainvoke(state)
    
    new_messages = result["messages"][original_count:]
    
    update = {"messages": new_messages}
    
    for key in ["backlog", "sprints", "project_report"]:
        if key in result and result[key]:
            update[key] = result[key]
    
    return update

async def create_scrum_agent_graph(config: Optional[RunnableConfig] = None):

    try:
        backlog_agent = await create_backlog_agent(config)
        sprint_agent = await create_sprint_agent(config)
        project_agent = await create_project_agent(config)
    except Exception as e:
        print(f"Error creating agents: {e}")
        return None
        
    agents_map = {
        "BacklogAgent": backlog_agent,
        "SprintAgent": sprint_agent,
        "ProjectAgent": project_agent
    }
    
    members = list(agents_map.keys())

    supervisor_agent = await create_team_supervisor(
        "gpt-4o",
        prompt,
        members,
    )

    graph = StateGraph(ScrumState)
    graph.add_node("Supervisor", supervisor_agent)
    
    for name in members:
        graph.add_node(name, agents_map[name])
        graph.add_edge(name, "Supervisor")
    
    graph.add_conditional_edges(
        "Supervisor",
        get_next_node,
        {**{name: name for name in members}, "FINISH": END}
    )
    
    graph.set_entry_point("Supervisor")

    return graph.compile(checkpointer=checkpointer)
