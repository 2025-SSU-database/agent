from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from dotenv import load_dotenv

from .user_input_analyzer import user_input_analyze_agent
from .backlog_maker import backlog_agent

load_dotenv()

@tool
async def analyze_user_input(request: str) -> str:
    """Analyze user input"""
    agent = await user_input_analyze_agent()
    result = await agent.ainvoke({
        "messages": [{ "role": "user", "content": request }],
    })

    return result["messages"][-1].text


@tool
def create_backlog(request: str) -> str:
    """Create backlog"""

    result = backlog_agent.invoke({
        "messages": [{"role": "user", "content": request}],
    })

    return result["messages"][-1].text


llm = ChatOpenAI(model="gpt-5")

tools = [analyze_user_input, create_backlog]

SUPERVISOR_PROMPT = (
    "You are a Scrum workflow supervisor that orchestrates the entire scrum schedule creation process."
    "You can analyze user input and create backlog."
    "Break down user requests into appropriate tool calls and coordinate the results. "
    "When a request involves multiple actions, use multiple tools in sequence."
)

supervisor_agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt=SUPERVISOR_PROMPT,
    name="Supervisor",
)

