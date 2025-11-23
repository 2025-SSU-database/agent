import json
from typing import List, TypedDict, Annotated, Optional
import operator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import RunnableConfig

from .team import create_backlog_team_graph, create_sprint_team_graph, create_team_supervisor

MODEL_NAME = "gpt-4o"

memory = MemorySaver()

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
    # Supervisor routing
    next: str
    # User input collection
    needs_user_input: bool  # Whether user input is needed
    user_question: Optional[str]  # Question to ask user


prompt = """
You are a Scrum Master supervisor tasked with coordinating between the Backlog Team and Sprint Team. Analyze the user's request and decide which team should act next.

Your teams:
- BacklogTeam: Handles creating/modifying use cases, epics, user stories, and tasks
- SprintTeam: Handles sprint planning and sprint schedule adjustments

IMPORTANT - Handling Information Requests:
- If ANY sub-graph (BacklogTeam or SprintTeam) requests additional information from the user (e.g., 프로젝트 기간, 팀 구성, 상세 기획 등), you MUST respond with FINISH.
- This allows the user to provide the missing information.
- Examples of missing info: 프로젝트 기간, 팀원 수/구성, 상세 기획, 기술 스택, 프로젝트 목표
- **Always ask questions and make requests in Korean.** (항상 한국어로 질문하고 요청하세요.)

Guidelines:
1. **Initial Request**: If the user asks to generate a backlog or plan a project, route to **BacklogTeam**.
2. **Backlog Completion**: If BacklogTeam has finished (look for "BacklogTeam completed work"), route to **SprintTeam**.
3. **Sprint Completion**: If SprintTeam has finished (look for "SprintTeam completed work"), and there are no further user requests, respond with **FINISH**.
4. **Refinement**: 
   - If the user specifically asks to modify backlog items, route to BacklogTeam.
   - If the user specifically asks to adjust the schedule, route to SprintTeam.

**CRITICAL**: Do NOT loop back to BacklogTeam after SprintTeam finishes unless the user explicitly asks for changes. If SprintTeam is done, just FINISH.

Analyze the conversation history to understand what has been done and what needs to be done next.
"""

def get_next_node(state: ScrumState) -> str:
    """Get the next node from supervisor's decision."""
    return state["next"]


async def create_scrum_agent_graph(config: Optional[RunnableConfig] = None):
    if config is None:
        config = RunnableConfig()

    backlog_team = await create_backlog_team_graph(config)
    sprint_team = await create_sprint_team_graph(config)
    
    # Define Nodes
    async def supervisor_node(state: ScrumState):

        supervisor_agent = await create_team_supervisor(
            MODEL_NAME,
            prompt,
            ["BacklogTeam", "SprintTeam"]
        )
        # Check if we just returned from collecting user input
        if state.get("needs_user_input"):
            # Reset the flag and continue processing
            return {"needs_user_input": False, "user_question": None}
        
        # Invoke supervisor to make routing decision
        result = supervisor_agent.invoke(state)
        
        # Check if the last message indicates need for user input
        messages = state.get("messages", [])
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, 'content') and "NEED_USER_INPUT:" in str(last_message.content):
                # Extract the question
                content = str(last_message.content)
                question = content.split("NEED_USER_INPUT:", 1)[1].strip()
                return {
                    "next": "FINISH",
                    "needs_user_input": True,
                    "user_question": question,
                    "messages": [AIMessage(content=question)]
                }
        
        # If Supervisor decided to FINISH and provided a reason, output it.
        if result.next == "FINISH" and result.reason:
             # Add the final schedule JSON if work is complete
            messages = [AIMessage(content=result.reason, name="Supervisor")]
            
            if state.get("sprints"):
                 schedule_data = {
                     "type": "schedule",
                     "sprints": state["sprints"]
                 }
                 # Add a separate message with JSON data
                 messages.append(AIMessage(content=json.dumps(schedule_data), name="ScheduleBot"))

            return {
                "next": result.next,
                "messages": messages
            }
        
        return {"next": result.next}
    
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
        
        response = await sprint_team.ainvoke({"tasks": tasks})
        
        return {
            "sprints": response.get("sprints", []),
            "messages": [AIMessage(content="SprintTeam completed work.", name="SprintTeam")]
        }

    # Build Graph
    graph = StateGraph(ScrumState)
    
    # Add nodes
    graph.add_node("Supervisor", supervisor_node)
    graph.add_node("BacklogTeam", backlog_node)
    graph.add_node("SprintTeam", sprint_node)
    
    # Set entry point to Supervisor
    graph.set_entry_point("Supervisor")
    
    # Add conditional edges from Supervisor
    graph.add_conditional_edges(
        "Supervisor",
        get_next_node,
        {
            "BacklogTeam": "BacklogTeam",
            "SprintTeam": "SprintTeam",
            "FINISH": END
        }
    )
    
    # Teams return to Supervisor after completion
    graph.add_edge("BacklogTeam", "Supervisor")
    graph.add_edge("SprintTeam", "Supervisor")
    
    return graph.compile(checkpointer=memory)
