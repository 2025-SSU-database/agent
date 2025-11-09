import sys
from pathlib import Path

from langgraph.constants import START, END
from typing_extensions import TypedDict
from typing import Annotated, Literal

from langgraph.graph import add_messages, StateGraph
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from src.agents.classifier import classifier
from src.agents.scrum import it_scrum_agent, general_scrum_agent
from src.agents.assistant import assistant_agent

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

async def it_scrum_node(state: State) -> State:
    """IT 스크럼 생성 에이전트 호출"""

    # 전체 messages를 전달하거나, 마지막 메시지의 텍스트만 추출
    result = await it_scrum_agent.ainvoke({
        "messages": state["messages"]
    })

    # 결과를 state에 추가
    return result


def general_scrum_node(state: State) -> State:
    """일반 스크럼 생성 에이전트 호출"""
    # 전체 messages를 전달하거나, 마지막 메시지의 텍스트만 추출
    result = general_scrum_agent.invoke({
        "messages": state["messages"]
    })

    # 결과를 state에 추가
    return result


def general_node(state: State) -> State:
    """일반 요청 처리 (placeholder)"""
    # 전체 messages를 전달
    result = assistant_agent.invoke({
        "messages": state["messages"]
    })

    return result


# LangGraph 구성
graph_builder = StateGraph(State)

# 노드 추가 (실제 작업을 수행하는 노드만)
graph_builder.add_node("it_scrum_agent", it_scrum_node)
graph_builder.add_node("general_scrum_agent", general_scrum_node)
graph_builder.add_node("general_agent", general_node)

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

# 그래프 컴파일
graph = graph_builder.compile()


if __name__ == '__main__':
    import asyncio
    
    # 테스트
    async def test_graph():
        test_it_scrum_request = "스포티파이 클론 프로젝트, 팀원: 1, 5, 기간: 오늘부터 3개월, 스포티파이를 클론하는 프로젝트입니다."
        test_general_scrum_request = "마케팅 캠페인 프로젝트, 팀원: 영업팀, 디자인팀, 기간: 2주"
        test_general_request = "안녕하세요, 파이썬에 대해 설명해주세요"

        print(f"\n🧪 테스트 시작: {test_it_scrum_request}\n")
        print("=" * 80)
        
        # 스트림 모드로 테스트
        async for event in graph.astream(
            {"messages": [{"role": "user", "content": test_it_scrum_request}]},
            stream_mode="updates"
        ):
            for node_name, node_data in event.items():
                print(f"\n🔄 노드 실행: {node_name}")
                if "messages" in node_data and len(node_data["messages"]) > 0:
                    last_msg = node_data["messages"][-1]
                    print(f"   메시지: {last_msg.content[:100]}...")
        
        print("\n" + "=" * 80)
        print("✅ 테스트 완료\n")
    
    asyncio.run(test_graph())