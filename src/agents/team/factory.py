from typing import Any
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI

from dotenv import load_dotenv

load_dotenv()

class AgentFactory:

  def __init__(self, model_name: str):
    self.llm = ChatOpenAI(model=model_name)
  
  async def create_agent_node(self, agent, name: str, callback: Any):

    async def agent_node(state):
      result = await agent.ainvoke(state)
      
      output = result.get("structured_response")

      updates = {}
      
      if output:
        updates = callback(output)
        content = f"Complete {name} work"
      else:
        content = result["messages"][-1].content

      updates["messages"] = [AIMessage(content=content, name=name)]
      
      return updates

    return agent_node

MODEL_NAME = "gpt-4o"

agent_factory = AgentFactory(model_name=MODEL_NAME)