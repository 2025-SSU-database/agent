from src.agents import create_graph
import asyncio
from langgraph.graph.state import RunnableConfig
from langchain_core.messages import HumanMessage, AIMessage
from src.utils import ainvoke_graph
import uuid
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
import json
import os
import argparse
from pathlib import Path

load_dotenv()

def load_test_cases(json_path: str = "test_cases.json") -> List[Dict[str, Any]]:
    """
    JSON 파일에서 테스트 케이스를 로드합니다.
    
    Args:
        json_path: JSON 파일 경로 (기본값: test_cases.json)
    
    Returns:
        테스트 케이스 리스트
    
    Raises:
        FileNotFoundError: JSON 파일이 없을 때
        json.JSONDecodeError: JSON 파싱 오류 시
    """
    json_file = Path(json_path)
    
    if not json_file.exists():
        raise FileNotFoundError(
            f"테스트 케이스 파일을 찾을 수 없습니다: {json_path}\n"
            f"기본 파일을 생성하려면 'test_cases.json' 파일을 생성하세요."
        )
    
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # JSON 구조 검증
    if not isinstance(data, list):
        raise ValueError("JSON 파일은 테스트 케이스 배열이어야 합니다.")
    
    # 각 테스트 케이스 검증
    for i, test_case in enumerate(data):
        if not isinstance(test_case, dict):
            raise ValueError(f"테스트 케이스 {i+1}번이 딕셔너리가 아닙니다.")
        if "name" not in test_case:
            raise ValueError(f"테스트 케이스 {i+1}번에 'name' 필드가 없습니다.")
        if "initial_message" not in test_case:
            raise ValueError(f"테스트 케이스 {i+1}번에 'initial_message' 필드가 없습니다.")
        if "steps" not in test_case:
            raise ValueError(f"테스트 케이스 {i+1}번에 'steps' 필드가 없습니다.")
        if not isinstance(test_case["steps"], list):
            raise ValueError(f"테스트 케이스 {i+1}번의 'steps'가 배열이 아닙니다.")
        
        # 각 step 검증
        for j, step in enumerate(test_case["steps"]):
            if not isinstance(step, dict):
                raise ValueError(f"테스트 케이스 {i+1}번의 step {j+1}번이 딕셔너리가 아닙니다.")
            if "response" not in step:
                raise ValueError(f"테스트 케이스 {i+1}번의 step {j+1}번에 'response' 필드가 없습니다.")
    
    return data


async def run_test_case(
    test_case: Dict[str, Any],
    config: RunnableConfig,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    단일 테스트 케이스를 실행합니다.
    
    Args:
        test_case: 테스트 케이스 딕셔너리 (name, initial_message, steps)
        config: RunnableConfig
        verbose: 상세 출력 여부
    
    Returns:
        테스트 결과 딕셔너리
    """
    if verbose:
        print("\n" + "=" * 80)
        print(f"🧪 테스트 케이스: {test_case['name']}")
        print("=" * 80)
    
    graph = await create_graph(config=config)
    step_index = 0
    all_steps_completed = []
    
    # 초기 메시지로 시작
    current_inputs = {
        "messages": [HumanMessage(content=test_case["initial_message"])]
    }
    
    if verbose:
        print(f"\n📝 초기 메시지: {test_case['initial_message']}")
        print("-" * 80)
    
    # 그래프 실행 및 단계별 진행
    max_iterations = 50  # 무한 루프 방지
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        # 그래프 실행 (스트리밍 완료까지 대기)
        await ainvoke_graph(graph, current_inputs, config)
        
        # 상태 확인
        state = graph.get_state(config)
        state_values = state.values if hasattr(state, 'values') else {}
        
        # 사용자 입력이 필요한지 확인
        needs_user_input = state_values.get("needs_user_input", False)
        user_question = state_values.get("user_question")
        
        if needs_user_input and user_question:
            if verbose:
                print(f"\n❓ [단계 {step_index + 1}] 에이전트 질문: {user_question}")
            
            # 테스트 케이스에 정의된 응답이 있는지 확인
            if step_index < len(test_case["steps"]):
                user_response = test_case["steps"][step_index]["response"]
                if verbose:
                    print(f"💬 [단계 {step_index + 1}] 사용자 응답: {user_response}")
                
                # 다음 단계를 위해 사용자 응답을 메시지로 추가
                current_inputs = {
                    "messages": [HumanMessage(content=user_response)]
                }
                
                all_steps_completed.append({
                    "step": step_index + 1,
                    "question": user_question,
                    "response": user_response
                })
                
                step_index += 1
            else:
                # 정의된 응답이 없으면 기본값 사용
                if verbose:
                    print(f"⚠️  테스트 케이스에 정의된 응답이 없습니다. 기본 응답을 사용합니다.")
                user_response = "알겠습니다."
                current_inputs = {
                    "messages": [HumanMessage(content=user_response)]
                }
                all_steps_completed.append({
                    "step": step_index + 1,
                    "question": user_question,
                    "response": user_response
                })
                step_index += 1
        else:
            # 완료 또는 다음 단계로 진행
            next_nodes = state.next if hasattr(state, 'next') else []
            
            # 완료 확인: next가 없거나 END인 경우
            if not next_nodes:
                # 테스트 완료
                if verbose:
                    print("\n✅ 테스트 케이스 완료")
                    print("-" * 80)
                
                # 최종 메시지 확인
                messages = state_values.get("messages", [])
                final_messages = []
                for msg in messages[-5:]:  # 마지막 5개 메시지만
                    if isinstance(msg, AIMessage):
                        content = str(msg.content)
                        final_messages.append({
                            "type": "ai",
                            "content": content[:200] + "..." if len(content) > 200 else content
                        })
                    elif isinstance(msg, HumanMessage):
                        content = str(msg.content)
                        final_messages.append({
                            "type": "human",
                            "content": content[:200] + "..." if len(content) > 200 else content
                        })
                
                return {
                    "test_case_name": test_case["name"],
                    "status": "completed",
                    "steps_completed": all_steps_completed,
                    "total_steps": len(test_case["steps"]),
                    "final_messages": final_messages,
                    "state_summary": {
                        "has_sprints": bool(state_values.get("sprints")),
                        "has_tasks": bool(state_values.get("tasks")),
                        "has_epics": bool(state_values.get("epics")),
                        "has_user_stories": bool(state_values.get("user_stories")),
                    }
                }
            else:
                # 다음 노드로 진행 중 - 사용자 입력이 필요하지 않으면 계속 진행
                if verbose:
                    print(f"\n🔄 다음 노드로 진행 중... (next: {next_nodes})")
                # 다음 실행을 위해 빈 입력 사용 (상태가 이미 업데이트됨)
                current_inputs = {"messages": []}
    
    # 최대 반복 횟수 초과
    if verbose:
        print(f"\n⚠️  최대 반복 횟수({max_iterations})에 도달했습니다.")
    
    return {
        "test_case_name": test_case["name"],
        "status": "max_iterations_reached",
        "steps_completed": all_steps_completed,
        "total_steps": len(test_case["steps"]),
    }


async def run_all_tests(
    test_cases: List[Dict[str, Any]],
    verbose: bool = True
) -> List[Dict[str, Any]]:
    """
    모든 테스트 케이스를 실행합니다.
    
    Args:
        test_cases: 테스트 케이스 리스트
        verbose: 상세 출력 여부
    
    Returns:
        테스트 결과 리스트
    """
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        # 각 테스트 케이스마다 새로운 thread_id 사용
        config = {
            "configurable": {
                "thread_id": str(uuid.uuid4()),
                "token": "eyJraWQiOiJRTHVWR1J4amJ4cVZwSUVHZWJTdWpvQWdjc1JOZ2FhckVucWFQcFJMRUM4PSIsImFsZyI6IlJTMjU2In0.eyJzdWIiOiJmNDk4YWQ3Yy0wMGIxLTcwNGUtMWEzYS1jMjRlOTJlMzdhNjUiLCJjb2duaXRvOmdyb3VwcyI6WyJhcC1ub3J0aGVhc3QtMl93VWVOTlN5RGRfR29vZ2xlIl0sImlzcyI6Imh0dHBzOlwvXC9jb2duaXRvLWlkcC5hcC1ub3J0aGVhc3QtMi5hbWF6b25hd3MuY29tXC9hcC1ub3J0aGVhc3QtMl93VWVOTlN5RGQiLCJ2ZXJzaW9uIjoyLCJjbGllbnRfaWQiOiIxcHF0YWRzc2llOWp2ZXQzZmZkZzI2cnZpNiIsIm9yaWdpbl9qdGkiOiJjMjVmZWZiOC0wMjJhLTRmOGQtYTYxMS02OGJjMzc2MDBkNGMiLCJ0b2tlbl91c2UiOiJhY2Nlc3MiLCJzY29wZSI6Im9wZW5pZCBlbWFpbCIsImF1dGhfdGltZSI6MTc2Mzk1Njk4OSwiZXhwIjoxNzY0MDA5MjY4LCJpYXQiOjE3NjQwMDU2NjgsImp0aSI6IjJjZDJiZGI0LTdmMTMtNGEyNC05NmZlLTY1NTI0NWJjNmNjNiIsInVzZXJuYW1lIjoiZ29vZ2xlXzExMzQwOTAwMTQ4NjAyMzM0ODUwNyJ9.igBZe_9GXuL_oeRLsb59RqXF-WyrbwBZWoTU1Ere1dJN-koTDW5eYKtIPfrArJ_3nJcuc2UghMsrJMSX2R8-CqbS1ZELuoc1rhLYGynv-ZCgfaBqMvVHeK8tLcE_tSFbwim-61XVvnotYl_ZlZ0fJ6fNB1YSJOTHYaH40G8kGzuipJF1UKAa_Z6QTXt5dMEjlZut17RHJUa-vWdG_tE0AMT0Fn9L5OBepYUbknknM6H6ynkOSOf11olkLSVBE9RKCOAUFvmg0-oyySQ4sEwthLOhJBerhizU03rGm4rFBL_9zDYWeLL8sFIwvrKfZR9xD7kspaFbIfXd0fwGyIcRVw"
            }
        }
        
        try:
            result = await run_test_case(test_case, config, verbose)
            result["test_index"] = i
            results.append(result)
        except Exception as e:
            if verbose:
                print(f"\n❌ 테스트 케이스 실행 중 오류 발생: {str(e)}")
            results.append({
                "test_case_name": test_case["name"],
                "test_index": i,
                "status": "error",
                "error": str(e)
            })
    
    return results


def print_test_summary(results: List[Dict[str, Any]]):
    """테스트 결과 요약을 출력합니다."""
    print("\n" + "=" * 80)
    print("📊 테스트 결과 요약")
    print("=" * 80)
    
    for result in results:
        status_emoji = "✅" if result.get("status") == "completed" else "❌"
        print(f"\n{status_emoji} {result.get('test_index', '?')}. {result.get('test_case_name', 'Unknown')}")
        print(f"   상태: {result.get('status', 'unknown')}")
        
        if result.get("status") == "completed":
            steps = result.get("steps_completed", [])
            print(f"   완료된 단계: {len(steps)}/{result.get('total_steps', 0)}")
            state_summary = result.get("state_summary", {})
            if any(state_summary.values()):
                print(f"   생성된 데이터: ", end="")
                data_types = []
                if state_summary.get("has_sprints"):
                    data_types.append("스프린트")
                if state_summary.get("has_tasks"):
                    data_types.append("태스크")
                if state_summary.get("has_epics"):
                    data_types.append("에픽")
                if state_summary.get("has_user_stories"):
                    data_types.append("사용자 스토리")
                print(", ".join(data_types) if data_types else "없음")
        elif result.get("status") == "error":
            print(f"   오류: {result.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 80)


async def main():
    """메인 함수"""
    # 명령줄 인자 파싱
    parser = argparse.ArgumentParser(description="에이전트 테스트 스크립트")
    parser.add_argument(
        "--test-cases",
        type=str,
        default="test_cases.json",
        help="테스트 케이스 JSON 파일 경로 (기본값: test_cases.json)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="테스트 결과를 저장할 JSON 파일 경로 (기본값: 저장하지 않음)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="상세 출력 비활성화"
    )
    
    args = parser.parse_args()
    
    try:
        # 테스트 케이스 로드
        print(f"📂 테스트 케이스 파일 로드 중: {args.test_cases}")
        test_cases = load_test_cases(args.test_cases)
        print(f"✅ {len(test_cases)}개의 테스트 케이스를 로드했습니다.\n")
        
        print("🚀 테스트 스크립트 시작")
        print(f"📋 총 {len(test_cases)}개의 테스트 케이스가 있습니다.\n")
        
        # 모든 테스트 실행
        results = await run_all_tests(test_cases, verbose=not args.quiet)
        
        # 결과 요약 출력
        if not args.quiet:
            print_test_summary(results)
        
        # JSON 파일로 결과 저장 (선택사항)
        if args.output:
            output_path = Path(args.output)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\n💾 테스트 결과가 저장되었습니다: {output_path}")
        
    except FileNotFoundError as e:
        print(f"❌ 오류: {e}")
        print("\n💡 예시 JSON 파일을 생성하려면 'test_cases.json' 파일을 생성하세요.")
        return 1
    except (json.JSONDecodeError, ValueError) as e:
        print(f"❌ JSON 파일 파싱 오류: {e}")
        return 1
    except Exception as e:
        print(f"❌ 예상치 못한 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)