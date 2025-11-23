import operator
from typing import Any, List, TypedDict, Annotated

from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode

from ..factory import agent_factory
from ..supervisor import create_team_supervisor
from ...mcp_utils import setup_mcp_tools
from langgraph.graph.state import RunnableConfig

from .use_case.agent import create_use_case_agent
from .epic.agent import create_epic_agent
from .user_story.agent import create_user_story_agent
from .task.agent import create_task_agent
from .tool import generate_backlog_items, estimate_effort, estimate_duration, collect_more_data_from_user

MODEL_NAME = "gpt-4o"

class BacklogState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next: str
    # Shared state for backlog items
    use_cases: Annotated[List[dict], operator.add]
    epics: Annotated[List[dict], operator.add]
    user_stories: Annotated[List[dict], operator.add]
    tasks: Annotated[List[dict], operator.add]

def get_next_node(state: BacklogState) -> str:
    return state["next"]

async def create_backlog_team_graph(config: RunnableConfig):

    async def use_case_node(state: BacklogState):
        use_case_agent = await create_use_case_agent(config)

        callback = lambda output: {
            "use_cases": [uc.model_dump() for uc in output.use_cases],
            "messages": [AIMessage(content=f"Created {len(output.use_cases)} use cases.", name="UseCaseAgent")]
        }

        node = await agent_factory.create_agent_node(use_case_agent, "UseCaseAgent", callback)
        return await node(state)

    async def epic_node(state: BacklogState):
        epic_agent = await create_epic_agent(config)

        callback = lambda output: {
            "epics": [epic.model_dump() for epic in output.epics],
            "messages": [AIMessage(content=f"Created {len(output.epics)} epics.", name="EpicAgent")]
        }

        node = await agent_factory.create_agent_node(epic_agent, "EpicAgent", callback)
        return await node(state)

    async def user_story_node(state: BacklogState):
        user_story_agent = await create_user_story_agent(config)

        callback = lambda output: {
            "user_stories": [us.model_dump() for us in output.user_stories],
            "messages": [AIMessage(content=f"Created {len(output.user_stories)} user stories.", name="UserStoryAgent")]
        }

        node = await agent_factory.create_agent_node(user_story_agent, "UserStoryAgent", callback)
        return await node(state)

    async def task_node(state: BacklogState):
        task_agent = await create_task_agent(config)

        callback = lambda output: {
            "tasks": [task.model_dump() for task in output.tasks],
            "messages": [AIMessage(content=f"Created {len(output.tasks)} tasks.", name="TaskAgent")]
        }

        node = await agent_factory.create_agent_node(task_agent, "TaskAgent", callback)
        return await node(state)
  
    members = ["UseCaseAgent", "EpicAgent", "UserStoryAgent", "TaskAgent"]

    # Supervisor 에이전트 생성
    supervisor_agent = await create_team_supervisor(
        model_name=MODEL_NAME,
        system_prompt=(
            "You are the supervisor of the Backlog Team. "
            "Your goal is to oversee the product backlog.\n\n"
            "**Team Members:**\n"
            "- UseCaseAgent: Defines use cases from requirements.\n"
            "- EpicAgent: Groups use cases into epics.\n"
            "- UserStoryAgent: Creates user stories from epics.\n"
            "- TaskAgent: Breaks down user stories into technical tasks.\n\n"
            "**Workflow Execution:**\n"
            "1. Start with **UseCaseAgent** to analyze requirements.\n"
            "2. Once use cases are defined, proceed to **EpicAgent**.\n"
            "3. After epics are created, move to **UserStoryAgent**.\n"
            "4. Finally, assign **TaskAgent** to generate tasks.\n\n"
            "**Rules:**\n"
            "- **Standard Flow**: For new requirements, maintain this order: UseCase -> Epic -> UserStory -> Task.\n"
            "- **Modifications**: If the user requests specific changes to existing items, you may route directly to the relevant agent.\n"
            "- **Handoff**: Route to the next agent ONLY after the current agent has successfully completed their output.\n"
            "- **Completion**: Do NOT finish the conversation until TaskAgent has completed the task breakdown.\n"
            "- If an agent asks for clarification, you may FINISH to return control to the user, but prefer resolving dependencies internally if possible.\n"
            "- If TaskAgent is done, respond with FINISH."
        ),
        members=members,
    )

    async def supervisor_node(state: BacklogState):
        result = await supervisor_agent.ainvoke(state)
        output = {"next": result.next}
        
        # If supervisor provides a reason/message, we might want to show it.
        if result.next == "FINISH" and result.reason:
             output["messages"] = [AIMessage(content=result.reason, name="Supervisor")]
             
        return output

    # 그래프 생성
    workflow = StateGraph(BacklogState)
    
    # 노드 추가
    workflow.add_node("UseCaseAgent", use_case_node)
    workflow.add_node("EpicAgent", epic_node)
    workflow.add_node("UserStoryAgent", user_story_node)
    workflow.add_node("TaskAgent", task_node)
    workflow.add_node("Supervisor", supervisor_node)
    
    for member in ["UseCaseAgent", "EpicAgent", "UserStoryAgent", "TaskAgent"]:
        workflow.add_edge(member, "Supervisor")

    # 조건부 엣지 추가 (Supervisor의 결정에 따라 라우팅)
    workflow.add_conditional_edges(
        "Supervisor",
        get_next_node,
        {**{m: m for m in members}, "FINISH": END},
    )

    workflow.set_entry_point("Supervisor")

    return workflow.compile(checkpointer=MemorySaver())
