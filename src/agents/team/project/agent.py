
from typing import List, TypedDict, Annotated, Optional
import operator
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.state import RunnableConfig
from langgraph.prebuilt import ToolNode, tools_condition

from .manager import create_project_manager_agent

from ...schema import Sprint, Backlog

class ProjectState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    sprints: List[Sprint]   
    tasks: List[Backlog]
    project_report: dict 

async def create_project_team_graph(config: Optional[RunnableConfig] = None):
    if config is None:
        config = RunnableConfig()
    
    project_manager_agent = await create_project_manager_agent(config)

    async def project_manager_node(state: ProjectState):
        messages = state.get("messages", [])
        
        if not messages:
            sprints = state.get("sprints", [])
            tasks = state.get("tasks", [])
            
            # Format input for the agent
            sprint_summary = f"Sprints: {len(sprints)}\n"
            for i, s in enumerate(sprints):
                 sprint_summary += f"Sprint {i+1}: {s}\n"
                 
            task_summary = f"Tasks: {len(tasks)}\n"
            # Limit task summary if too long
            for i, t in enumerate(tasks[:50]): 
                 task_summary += f"- {t}\n"
            if len(tasks) > 50:
                task_summary += "...(more tasks)..."
            
            input_str = f"Analyze the following:\n\n{sprint_summary}\n\n{task_summary}"
            inputs = {"messages": [HumanMessage(content=input_str)]}
        else:
            inputs = {"messages": messages}
        
        response = await project_manager_agent.ainvoke(inputs)
        
        output = response.get("structured_response")
        
        if output:
            return {
                "project_report": output.model_dump(),
                "messages": response['messages'] + [AIMessage(content=f"ProjectManager completed work.", name="ProjectManager")]
            }
        
        # Otherwise, it might be a tool call or intermediate thought.
        return {
            "messages": response['messages']
        }

    graph = StateGraph(ProjectState)
    graph.add_node("ProjectManager", project_manager_node)
    
    graph.add_edge("ProjectManager", END)

    graph.set_entry_point("ProjectManager")
    
    return graph.compile()
