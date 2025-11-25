import operator
from typing import Any, List, TypedDict, Annotated, Dict

from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.constants import Send
from langchain_core.runnables import RunnableConfig

from ..factory import agent_factory
from ..supervisor import create_team_supervisor

from .use_case.agent import create_use_case_agent
from .epic.agent import create_epic_agent
from .user_story.agent import create_user_story_agent
from .task.agent import create_task_agent
from ...schema import Backlog

MODEL_NAME = "gpt-4o"

class BacklogState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next: str
    # Shared state for backlog items
    use_cases: Annotated[List[str], operator.add]
    epics: Annotated[List[str], operator.add]
    user_stories: Annotated[List[str], operator.add]
    tasks: Annotated[List[Backlog], operator.add]

# Input states for parallel execution
class EpicInputState(TypedDict):
    use_case: str

class UserStoryInputState(TypedDict):
    epic: str

class TaskInputState(TypedDict):
    user_story: str

class UserStorySubgraphState(TypedDict):
    epic: str
    # Outputs and bubbled-up outputs
    user_stories: Annotated[List[str], operator.add]
    tasks: Annotated[List[Backlog], operator.add]
    messages: Annotated[List[BaseMessage], operator.add]

def get_next_node(state: BacklogState) -> str:
    return state["next"]

async def create_backlog_team_graph(config: RunnableConfig):
    
    members = ["UseCaseAgent", "EpicAgent", "UserStoryAgent", "TaskAgent"]
    
    supervisor_agent = await create_team_supervisor(
        model_name=MODEL_NAME,
        system_prompt=(
            "You are the supervisor of the Backlog Team.\n"
            "Your goal is to oversee the product backlog creation.\n\n"
            "**Team Members:**\n"
            "- BacklogGeneration: A specialized subsystem that automatically generates Use Cases, Epics, User Stories, and Tasks in parallel.\n\n"
            "**Workflow:**\n"
            "1. Upon request to generate a backlog, delegate to **BacklogGeneration**.\n"
            "2. Wait for it to complete. It will produce the entire hierarchy.\n"
            "3. Once done, review or FINISH.\n"
            "4. If the user asks for specific modifications, you may need to handle it (but currently we only support full generation via this flow).\n"
        ),
        members=members,
    )

    # Main Workflow
    workflow = StateGraph(BacklogState)
    workflow.add_node("Supervisor", supervisor_agent)
    
    
    workflow.set_entry_point("Supervisor")

    return workflow.compile()
