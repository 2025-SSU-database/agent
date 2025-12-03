import operator
from typing import List, Literal, Optional
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict, Annotated

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

async def create_interactive_agent(
    model: BaseChatModel,
    frontend_tools: List[BaseTool],
    backend_tools: List[BaseTool],
    system_prompt: Optional[str] = None
):
    all_tools = frontend_tools + backend_tools
    model_with_tools = model.bind_tools(all_tools)

    def call_model(state: AgentState):
        messages = state["messages"]
        
        if system_prompt:
            messages = [SystemMessage(content=system_prompt)] + messages
            
        response = model_with_tools.invoke(messages)
        return {"messages": [response]}

    backend_tool_node = ToolNode(backend_tools)

    def router(state: AgentState) -> Literal["tools", END]:
        messages = state["messages"]
        last_message = messages[-1]

        if not last_message.tool_calls:
            return END

        tool_call = last_message.tool_calls[0]
        tool_name = tool_call["name"]

        if any(t.name == tool_name for t in frontend_tools):
            return END
        
        return "tools"

    workflow = StateGraph(AgentState)

    workflow.add_node("agent", call_model)
    workflow.add_node("tools", backend_tool_node)

    workflow.set_entry_point("agent")

    workflow.add_conditional_edges(
        "agent",
        router,
        {
            "tools": "tools",
            END: END
        }
    )

    workflow.add_edge("tools", "agent")

    return workflow.compile(interrupt_before=["tools"])