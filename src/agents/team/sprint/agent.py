from typing import List, TypedDict, Optional, Annotated
import operator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.state import RunnableConfig

from ...schema import Sprint, Backlog   
from .planning import create_sprint_planning_agent

class SprintState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    tasks: Annotated[List[Backlog], operator.add]
    sprints: Annotated[List[Sprint], operator.add]

async def create_sprint_team_graph(config: Optional[RunnableConfig] = None):
    if config is None:
        config = RunnableConfig()

    # Initialize Agents
    sprint_planning_agent = await create_sprint_planning_agent(config)
    
    # Define Nodes
    async def sprint_planning_node(state: SprintState):
        # If there are no messages, this is the first turn. Prepare the initial prompt.
        messages = state.get("messages", [])
        if not messages:
            tasks = state.get("tasks", [])
            task_summaries = []
            for t in tasks:
                if isinstance(t, dict):
                    title = t.get("title", "Unknown")
                    effort = t.get("estimated_effort_hours", "N/A")
                else:
                    title = getattr(t, "title", "Unknown")
                    effort = getattr(t, "estimated_effort_hours", "N/A")
                task_summaries.append(f"- {title} (Effort: {effort}h)")
            tasks_str = "\n".join(task_summaries)
            
            msg = f"Plan sprints for the following tasks:\n{tasks_str}"
            inputs = {"messages": [HumanMessage(content=msg)]}
        else:
            # If we have history (e.g., returned from tool execution), pass it along.
            inputs = state

        response = await sprint_planning_agent.ainvoke(inputs)
        
        # If the agent produced the final structured output, process it.
        output = response.get('structured_response')
        if output:
            sprints = [sprint.model_dump() for sprint in output.sprints]
            return {
                "sprints": sprints, 
                "messages": response['messages'] + [AIMessage(content=f"Created {len(sprints)} sprints")]
            }
        
        # Otherwise, it might be a tool call or intermediate thought. Update state with new messages.
        return {"messages": response['messages']}

    # Build Graph
    graph = StateGraph(SprintState)
    
    graph.add_node("SprintPlanningNode", sprint_planning_node)

    graph.set_entry_point("SprintPlanningNode")
    
    graph.add_edge("SprintPlanningNode", END)

    return graph.compile()
