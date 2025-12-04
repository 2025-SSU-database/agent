from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph.state import RunnableConfig
from langchain.agents import create_agent
from langgraph.types import interrupt

from ..hand_off_agent import create_interactive_agent
from .prompt import prompt
from ..mcp_utils import setup_mcp_tools

@tool
def request_workspace_selection() -> dict:
    """
    Request the user to select a workspace.
    Use this tool when you need a workspace_id to proceed (e.g., for creating a project) but one was not provided or is ambiguous.
    """
    workspace_id = interrupt("select workspace")

    return workspace_id

@tool
def request_project_selection() -> dict:
    """
    Request the user to select a project within a specific workspace.
    Use this tool when you need a project_id to proceed (e.g., for creating a backlog) but one was not provided or is ambiguous.
    """
    
    project_id = interrupt("select project_id")

    return project_id

async def create_project_agent(config: RunnableConfig):
    # 타임아웃 및 재시도 설정 추가
    llm = ChatOpenAI(
        model="gpt-4o", 
        use_responses_api=True,
        timeout=120,  # 120초 타임아웃
        max_retries=3,  # 최대 3번 재시도
        request_timeout=120,  # 요청 타임아웃 120초
        name="ProjectAgent",
    )
    tools = [request_workspace_selection, request_project_selection]

    mcp_tools = await setup_mcp_tools(config)

    # agent = await create_interactive_agent(
    #     model=llm,
    #     frontend_tools=tools,
    #     backend_tools=mcp_tools,
    #     system_prompt=prompt,
    # )

    agent = create_agent(
        model="gpt-4o",
        tools=[*tools, *mcp_tools],
        system_prompt=prompt,
    )

    return agent