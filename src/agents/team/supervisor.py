from typing import Literal, List, Any, Optional, Dict
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

async def create_team_supervisor(
  model_name, 
  system_prompt, 
  members, 
  mcp_list: Optional[List[Dict[str, Any]]] = None, 
  tools: Optional[List[Any]] = None
):
  options_for_next = ["FINISH"] + members

  class RouteResponse(BaseModel):
    next: Literal[*options_for_next]
    reason: str = Field(description="The reason for the routing decision. If FINISH, this should be a helpful message to the user explaining what is needed or what was done.")

  prompt = ChatPromptTemplate.from_messages(
    [
      ("system", system_prompt),
      MessagesPlaceholder(variable_name="messages"),
      (
        "system",
        "Given the conversation above, who should act next? "
        "If any agent want more information from the user, FINISH and ask to human to provide more information with reason"
        "Or should we FINISH? Select one of: {options}."
      ),
    ]
  ).partial(options=str(options_for_next))

  tools = []
  
  if tools:
    tools.extend(tools)

  if mcp_list:
    client = MultiServerMCPClient(*mcp_list)
    mcp_tools = await client.get_tools()

    print(f"Successfully loaded {len(mcp_tools)} MCP tools")
    
    tools.extend(mcp_tools)

  else:
    print("No MCP tools provided")

  llm = ChatOpenAI(model=model_name)
  
  if tools:
    llm = llm.bind_tools(tools)
  
  supervisor_chain = prompt | llm.with_structured_output(RouteResponse)

  return supervisor_chain
