from math import degrees
import sys
from pathlib import Path

from langgraph.constants import START, END
from typing_extensions import TypedDict
from typing import Annotated, Literal

from langgraph.graph import add_messages, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .classifier import classifier
from .scrum import it_scrum_agent, general_scrum_agent
from .assistant import assistant_agent

load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

class State(TypedDict):
    messages: Annotated[list, add_messages]
    request_type: str  # "scrum" or "general"

# LLM 초기화
llm = ChatOpenAI(model="gpt-4o")

def classify_request(state: State) -> Literal["it_scrum_agent", "general_scrum_agent", "general_agent"]:
    """사용자 요청을 분류 (라우팅 함수)"""

    last_message = state["messages"][-1]
    # Message 객체에서 텍스트 내용만 추출
    message_text = last_message.content if isinstance(last_message.content, str) else str(last_message.content)

    response = classifier.invoke({
        "message": message_text,
    })

    print(f"🔍 분류 결과: {response.classification}")

    return response.classification

# 싱글톤 그래프 인스턴스
_graph_instance = None

async def _initialize_graph():
    """그래프를 처음 한 번만 생성 (async 초기화 필요)"""
    global _graph_instance

    # LangGraph 구성
    graph_builder = StateGraph(State)

    checkpoint = MemorySaver()

    it_scrum_node = await it_scrum_agent()
    general_scrum_node = general_scrum_agent

    # 노드 추가 (실제 작업을 수행하는 노드만)
    graph_builder.add_node("it_scrum_agent", it_scrum_node)
    graph_builder.add_node("general_scrum_agent", general_scrum_node)
    graph_builder.add_node("general_agent", assistant_agent)

    # 조건부 엣지 추가 (START에서 분류 후 해당 에이전트로 라우팅)
    graph_builder.add_conditional_edges(
        START,
        classify_request,
        {
            "it_scrum": "it_scrum_agent",
            "general_scrum": "general_scrum_agent",
            "general": "general_agent"
        }
    )

    # 다른 노드에서 종료
    graph_builder.add_edge("it_scrum_agent", END)
    graph_builder.add_edge("general_scrum_agent", END)
    graph_builder.add_edge("general_agent", END)

    # Checkpoint 설정 (interrupt를 지원하기 위해 필요)

    # 그래프 컴파일
    _graph_instance = graph_builder.compile(checkpointer=checkpoint)
    return _graph_instance

async def get_graph():
    """싱글톤 그래프 인스턴스 반환"""
    global _graph_instance
    if _graph_instance is None:
        await _initialize_graph()
    return _graph_instance