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

    # --- Node Implementations ---

    async def use_case_node(state: BacklogState):
        use_case_agent = await create_use_case_agent(config)
        
        # create_agent에서 이미 interrupt_before=["tools"]가 설정되어 있음
        result = await use_case_agent.ainvoke(state, config=config)
        
        output = result.get("structured_response")
        
        if not output:
            return {"messages": [AIMessage(content="Failed to generate use cases.", name="UseCaseAgent")]}

        return {
            "use_cases": output.use_cases,
            "messages": [AIMessage(content=f"Created {len(output.use_cases)} use cases.", name="UseCaseAgent")]
        }

    async def epic_node(state: EpicInputState):
        epic_agent = await create_epic_agent(config)
        use_case = state["use_case"]
        
        # Create context for the agent
        msg_content = f"""Generate epics for the following use case:
        
        Title: {use_case.title}
        Description: {use_case.description}
        Business Value: {use_case.business_value}
        """
        
        # create_agent에서 이미 interrupt_before=["tools"]가 설정되어 있음
        result = await epic_agent.ainvoke(
            {"messages": [HumanMessage(content=msg_content)]},
            config=config
        )
        
        output = result.get("structured_response")
        
        if not output:
            return {"epics": []} 

        return {
            "epics": output.epics,
            "messages": [AIMessage(content=f"Created {len(output.epics)} epics for use case '{use_case.title}'.", name="EpicAgent")]
        }

    async def user_story_node(state: UserStoryInputState):
        user_story_agent = await create_user_story_agent(config)
        epic = state["epic"]
        
        msg_content = f"""Generate user stories for the following epic:
        
        Title: {epic.title}
        Description: {epic.description}
        Estimated Effort: {epic.estimated_effort}
        """
        
        # create_agent에서 이미 interrupt_before=["tools"]가 설정되어 있음 (tools가 있는 경우)
        result = await user_story_agent.ainvoke(
            {"messages": [HumanMessage(content=msg_content)]},
            config=config
        )
        
        output = result.get("structured_response")
        
        if not output:
            return {"user_stories": []}

        return {
            "user_stories": output.user_stories,
            "messages": [AIMessage(content=f"Created {len(output.user_stories)} user stories for epic '{epic.title}'.", name="UserStoryAgent")]
        }

    async def task_node(state: TaskInputState):
        task_agent = await create_task_agent(config)
        user_story = state["user_story"]
        
        msg_content = f"""Generate tasks for the following user story:
        
        Title: {user_story.title}
        Description: {user_story.description}
        Acceptance Criteria: {user_story.acceptance_criteria}
        """
        
        # create_agent에서 이미 interrupt_before=["tools"]가 설정되어 있음
        result = await task_agent.ainvoke(
            {"messages": [HumanMessage(content=msg_content)]},
            config=config
        )
        
        output = result.get("structured_response")
        
        if not output:
            return {"tasks": []}

        return {
            "tasks": output.tasks,
            "messages": [AIMessage(content=f"Created {len(output.tasks)} tasks for user story '{user_story.title}'.", name="TaskAgent")]
        }


    async def user_story_node_wrapper(state: UserStorySubgraphState):
        # Wrapper to match the input/output types
        res = await user_story_node(state) # expects 'epic' in state
        return res # returns {'user_stories': ..., 'messages': ...}


    user_story_workflow = StateGraph(UserStorySubgraphState)
    user_story_workflow.add_node("UserStoryAgent", user_story_node_wrapper)
    user_story_workflow.add_node("TaskAgent", task_node)
    
    def map_stories_to_tasks(state: UserStorySubgraphState):
        return [Send("TaskAgent", {"user_story": us}) for us in state.get("user_stories", [])]
        
    user_story_workflow.add_conditional_edges("UserStoryAgent", map_stories_to_tasks, ["TaskAgent"])
    user_story_workflow.set_entry_point("UserStoryAgent")
    
    # 3. Epic Graph (Input: UseCase -> Output: Epics -> Send(UserStoryGraph))
    
    class EpicSubgraphState(TypedDict):
        use_case: str
        # Outputs
        epics: Annotated[List[str], operator.add]
        user_stories: Annotated[List[str], operator.add]
        tasks: Annotated[List[Backlog], operator.add]
        messages: Annotated[List[BaseMessage], operator.add]

    async def epic_node_wrapper(state: EpicSubgraphState):
        res = await epic_node(state) # expects 'use_case'
        return res # returns {'epics': ..., 'messages': ...}

    epic_workflow = StateGraph(EpicSubgraphState)
    epic_workflow.add_node("EpicAgent", epic_node_wrapper)
    
    # Add the UserStoryGraph as a node
    epic_workflow.add_node("UserStoryGraph", user_story_workflow.compile())
    
    def map_epics_to_stories(state: EpicSubgraphState):
        return [Send("UserStoryGraph", {"epic": e}) for e in state.get("epics", [])]
        
    epic_workflow.add_conditional_edges("EpicAgent", map_epics_to_stories, ["UserStoryGraph"])
    epic_workflow.set_entry_point("EpicAgent")
    
    backlog_gen_workflow = StateGraph(BacklogState)
    backlog_gen_workflow.add_node("UseCaseAgent", use_case_node)
    backlog_gen_workflow.add_node("EpicGraph", epic_workflow.compile())
    
    def map_cases_to_epics(state: BacklogState):
        return [Send("EpicGraph", {"use_case": uc}) for uc in state.get("use_cases", [])]
        
    backlog_gen_workflow.add_conditional_edges("UseCaseAgent", map_cases_to_epics, ["EpicGraph"])
    backlog_gen_workflow.set_entry_point("UseCaseAgent")
    
    backlog_gen_graph = backlog_gen_workflow.compile()

    # --- Main Supervisor Graph ---
    
    members = ["BacklogGeneration"]
    
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
    workflow.add_node("BacklogGeneration", backlog_gen_graph)
    
    workflow.add_edge("BacklogGeneration", "Supervisor")
    
    workflow.add_conditional_edges(
        "Supervisor",
        get_next_node,
        {"BacklogGeneration": "BacklogGeneration", "FINISH": END}
    )
    
    workflow.set_entry_point("Supervisor")

    return workflow.compile()
