import operator
import json
import os
from typing import TypedDict, Optional
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage
from typing_extensions import Annotated
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient

from dotenv import load_dotenv

from .user_input_analyzer import create_user_input_analyzer
from .backlog_maker import create_backlog_generator
from .sprints_maker import create_sprint_planner    
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

load_dotenv()

class State(TypedDict, total=False):
    """
    스크럼 계획 생성 워크플로우의 상태

    필수 필드:
    - messages: 대화 이력 (모든 단계에서 누적됨)

    점진적 추가 (각 단계에서 생성):
    - analyze_user_input: project_name, duration, team_members, requirements
    - create_backlog: backlog
    - create_sprints: sprints
    """
    # 항상 필요
    messages: Annotated[list[AnyMessage], operator.add]

    # 1단계: 사용자 입력 분석 (analyze_user_input에서 추가)
    project_name: Optional[str]
    duration: Optional[str]
    team_members: Optional[list[dict]]
    requirements: Optional[str]

    # 2단계: 백로그 생성 (create_backlog에서 추가)
    backlog: Optional[list[dict]]

    # 3단계: 스프린트 계획 (create_sprints에서 추가)
    sprints: Optional[list[dict]]


def extract_json_from_message(message: AnyMessage) -> Optional[dict]:
    """메시지에서 JSON을 추출"""
    if isinstance(message, AIMessage):
        content = message.content
        if isinstance(content, str):
            # JSON 코드 블록에서 추출
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                json_str = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                json_str = content[start:end].strip()
            else:
                json_str = content.strip()

            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                return None
    return None


def extract_pydantic_to_dict(data):
    """Pydantic 모델을 dict로 변환"""
    if isinstance(data, dict):
        return data
    elif hasattr(data, "dict"):
        return data.dict()
    elif hasattr(data, "model_dump"):
        return data.model_dump()
    return data

async def extract_user_input_data(state: State) -> State:
    """Extract user input data from messages"""
    # 마지막 메시지에서 JSON 추출
    if state.get("messages"):
        last_message = state["messages"][-1]
        extracted_data = extract_json_from_message(last_message)
        
        if extracted_data:
            update = {}
            if "project_name" in extracted_data:
                update["project_name"] = extracted_data["project_name"]
            if "duration" in extracted_data:
                update["duration"] = extracted_data["duration"]
            if "team_members" in extracted_data:
                update["team_members"] = extracted_data["team_members"]
            if "requirements" in extracted_data:
                update["requirements"] = extracted_data["requirements"]
            return update
    
    return {}

async def extract_backlog_data(state: State) -> State:
    """Extract backlog data from messages"""
    # 필수 정보 확인
    if not state.get("project_name") or not state.get("requirements"):
        missing = []
        if not state.get("project_name"):
            missing.append("프로젝트명")
        if not state.get("requirements"):
            missing.append("요구사항")
        error_msg = f"백로그 생성을 위해 필요한 정보: {', '.join(missing)}"
        print(f"⚠️ {error_msg}")
        interrupt(error_msg)

    # 마지막 메시지에서 JSON 추출
    if state.get("messages"):
        last_message = state["messages"][-1]
        extracted_data = extract_json_from_message(last_message)
        
        if extracted_data and "items" in extracted_data:
            backlog_items = []
            for item in extracted_data.get("items", []):
                backlog_items.append(extract_pydantic_to_dict(item))
            return {"backlog": backlog_items}
    
    return {}


async def extract_sprints_data(state: State) -> State:
    """Extract sprints data from messages"""
    # 백로그 확인
    if not state.get("backlog") or len(state.get("backlog", [])) == 0:
        error_msg = "백로그가 없습니다. 먼저 백로그를 생성해주세요."
        print(f"⚠️ {error_msg}")
        interrupt(error_msg)

    # 마지막 메시지에서 JSON 추출
    if state.get("messages"):
        last_message = state["messages"][-1]
        extracted_data = extract_json_from_message(last_message)
        
        if extracted_data and "sprints" in extracted_data:
            sprints = []
            for sprint in extracted_data.get("sprints", []):
                sprints.append(extract_pydantic_to_dict(sprint))
            return {"sprints": sprints}
    
    return {}


async def generate_final_output(state: State) -> State:
    """Generate final scrum output"""
    scrum_info = {
        "project_name": state.get("project_name", ""),
        "duration": state.get("duration", ""),
        "team_members": state.get("team_members", []),
        "requirements": state.get("requirements", ""),
        "backlog": state.get("backlog", []),
        "sprints": state.get("sprints", []),
    }

    final_output = json.dumps(scrum_info, ensure_ascii=False, indent=2)

    final_message = AIMessage(
        content=f"""# 스크럼 계획 최종 결과

{final_output}

## 요약
- **프로젝트**: {scrum_info.get('project_name', 'N/A')}
- **기간**: {scrum_info.get('duration', 'N/A')}
- **팀원**: {len(scrum_info.get('team_members', []))}명
- **백로그**: {len(scrum_info.get('backlog', []))}개
- **스프린트**: {len(scrum_info.get('sprints', []))}개"""
    )

    return {"messages": [final_message]}


async def create_scrum(state: State) -> State:
    """Create scrum in actual service"""
    scrum_data = {
        "project_name": state.get("project_name", ""),
        "duration": state.get("duration", ""),
        "team_members": state.get("team_members", []),
        "requirements": state.get("requirements", ""),
        "backlog": state.get("backlog", []),
        "sprints": state.get("sprints", []),
    }

    # 사용자 승인 요청
    is_approved = interrupt("스크럼 데이터를 서비스에 저장하시겠습니까?")

    # MCP 서버를 통해 저장
    mcp_url = os.getenv("ZENIOR_MCP_SERVER_URL")

    if not mcp_url:
        error_message = AIMessage(
            content="⚠️ MCP_SERVER_URL 환경 변수가 설정되지 않았습니다."
        )
        return {"messages": [error_message]}

    try:
        client = MultiServerMCPClient(
            {"zenior": {"transport": "streamable_http", "url": mcp_url}}
        )
        mcp_tools = await client.get_tools()

        # 스크럼 생성 도구 찾기
        scrum_tool = None
        for tool in mcp_tools:
            if any(
                keyword in tool.name.lower()
                for keyword in ["scrum", "project", "create"]
            ):
                scrum_tool = tool
                break

        if scrum_tool:
            try:
                result = await scrum_tool.ainvoke(scrum_data)
                success_message = AIMessage(
                    content=f"""✅ 스크럼 데이터 저장 완료

프로젝트: {scrum_data['project_name']}
백로그: {len(scrum_data['backlog'])}개
스프린트: {len(scrum_data['sprints'])}개"""
                )
                return {"messages": [success_message]}
            except Exception as e:
                error_message = AIMessage(content=f"❌ 저장 실패: {str(e)}")
                return {"messages": [error_message]}
        else:
            warning_message = AIMessage(
                content="⚠️ 스크럼 생성 도구를 찾을 수 없습니다."
            )
            return {"messages": [warning_message]}

    except Exception as e:
        error_message = AIMessage(
            content=f"⚠️ MCP 서버 연결 실패: {str(e)}"
        )
        return {"messages": [error_message]}

async def create_supervisor():
    user_input_analyzer = await create_user_input_analyzer()
    backlog_generator = await create_backlog_generator()
    sprint_planner = await create_sprint_planner()
    
    # 그래프 생성
    graph_builder = StateGraph(State)

    graph_builder.add_node("user_input_analyzer", user_input_analyzer)
    graph_builder.add_node("extract_user_input_data", extract_user_input_data)
    graph_builder.add_node("backlog_generator", backlog_generator)
    graph_builder.add_node("sprint_planner", sprint_planner)
    graph_builder.add_node("generate_final_output", generate_final_output)
    graph_builder.add_node("create_scrum", create_scrum)

    graph_builder.add_edge(START, "user_input_analyzer")
    graph_builder.add_edge("user_input_analyzer", "extract_user_input_data")
    graph_builder.add_edge("extract_user_input_data", "backlog_generator")
    graph_builder.add_edge("backlog_generator", "sprint_planner")
    graph_builder.add_edge("sprint_planner", "generate_final_output")
    graph_builder.add_edge("generate_final_output", "create_scrum")
    graph_builder.add_edge("create_scrum", END)

    return graph_builder.compile()
