from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import json
from typing import AsyncGenerator
import sys
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.main import graph

app = FastAPI()

# CORS 설정 (프론트엔드에서 접근할 경우)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


@app.get("/")
def hello_world():
    return {"message": "Hello World"}


@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/agent/stream")
async def zenior_agent_stream(request: ChatRequest):
    """스트리밍 방식으로 에이전트 응답 반환 - 각 노드/툴 실행마다 업데이트"""
    
    async def generate_response() -> AsyncGenerator[str, None]:
        try:
            print(f"🚀 스트림 시작: {request.message[:50]}...")
            
            # LangGraph 스트림 실행 (updates 모드: 각 노드가 실행될 때마다 업데이트)
            async for event in graph.astream(
                {"messages": [{"role": "user", "content": request.message}]},
                stream_mode="updates"  # 노드별 업데이트 받기
            ):
                print(f"📦 이벤트 수신: {list(event.keys())}")
                
                # event 구조: {node_name: state_update}
                for node_name, node_update in event.items():
                    # 노드 시작 이벤트
                    node_event = {
                        "event_type": "node_update",
                        "node": node_name,
                        "timestamp": None
                    }
                    
                    # 메시지가 있으면 추가
                    if "messages" in node_update and len(node_update["messages"]) > 0:
                        last_message = node_update["messages"][-1]
                        node_event["message"] = {
                            "type": last_message.__class__.__name__,
                            "content": last_message.content,
                        }
                    
                    # request_type이 있으면 추가 (분류 결과)
                    if "request_type" in node_update:
                        node_event["request_type"] = node_update["request_type"]
                    
                    print(f"📤 전송: 노드={node_name}")
                    
                    # SSE 형식으로 전송
                    yield f"data: {json.dumps(node_event, ensure_ascii=False)}\n\n"
            
            print("✅ 스트림 완료")
            # 스트림 종료 신호
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            import traceback
            print(f"❌ 에러 발생: {e}")
            error_msg = {
                "event_type": "error",
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            yield f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # nginx 버퍼링 비활성화
        }
    )


@app.post("/agent")
async def zenior_agent(request: ChatRequest):
    """일반 방식으로 에이전트 응답 반환 (스트리밍 없이)"""
    try:
        result = await graph.ainvoke({
            "messages": [{"role": "user", "content": request.message}]
        })
        
        # 마지막 메시지 추출
        if "messages" in result and len(result["messages"]) > 0:
            last_message = result["messages"][-1]
            return {
                "type": last_message.__class__.__name__,
                "content": last_message.content,
            }
        
        return {"error": "No response generated"}
    
    except Exception as e:
        return {"error": str(e)}


if __name__ == '__main__':
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info",
        access_log=False  # 액세스 로그 비활성화로 버퍼링 감소
    )