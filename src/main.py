from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
import uvicorn
import json
from typing import AsyncGenerator, Optional
import sys
from pathlib import Path
import uuid
from langgraph.types import Command
from contextlib import asynccontextmanager

from agents import get_graph  

# 프로젝트 루트를 PYTHONPATH에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def serialize_chunk(chunk_data):
    """chunk 데이터를 JSON으로 직렬화 (Interrupt 객체 처리 포함)"""
    def default_serializer(obj):
        # Interrupt 객체 처리
        if hasattr(obj, 'value') and hasattr(obj, 'id'):
            return {'value': obj.value, 'id': str(obj.id)}
        # 기타 객체는 문자열로 변환
        return str(obj)
    
    try:
        return json.dumps(chunk_data, default=default_serializer, ensure_ascii=False)
    except Exception as e:
        # 직렬화 실패 시 안전하게 처리
        try:
            return json.dumps({'error': f'Serialization error: {str(e)}', 'data': str(chunk_data)}, ensure_ascii=False)
        except:
            return json.dumps({'error': 'Failed to serialize data'}, ensure_ascii=False)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 앱 시작 및 종료 시 실행"""
    # 시작: 그래프 싱글톤 초기화
    print("🚀 그래프 초기화 중...")
    await get_graph()
    print("✅ 그래프 초기화 완료")

    yield  # 앱 실행 중

    # 종료: 필요시 정리 작업 수행
    print("👋 앱 종료")

app = FastAPI(lifespan=lifespan)

# 정적 파일 서빙 (HTML 클라이언트)
static_dir = project_root / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

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
    thread_id: Optional[str] = None  # 세션 관리를 위한 thread_id


class ResumeRequest(BaseModel):
    thread_id: str
    # HITL 스타일 결정
    decisions: Optional[list[dict]] = None  # [{"type": "approve|edit|reject", ...}]
    # 레거시 지원
    approved: Optional[bool] = None  # 사용자 승인 여부
    user_response: Optional[str] = None  # 사용자 응답 (추가 정보 제공 시)


@app.get("/")
async def root():
    """채팅 클라이언트 페이지"""
    static_file = project_root / "static" / "index.html"
    if static_file.exists():
        return FileResponse(str(static_file))
    return {"message": "Hello World", "chat_client": "/static/index.html"}


@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/chat/stream")
async def agent_stream(request: ChatRequest):
    # Thread ID 생성 또는 기존 ID 사용
    thread_id = request.thread_id or str(uuid.uuid4())

    print(f"🚀 스트림 시작: {request.message[:50]}... (thread_id: {thread_id})")

    config = {"configurable": {"thread_id": thread_id}}

    async def event_stream():
        try:
            graph = await get_graph()
            # 스트림 시작 시 thread_id를 클라이언트에 전송
            yield f"data: {json.dumps({'event_type': 'thread_id', 'thread_id': thread_id}, ensure_ascii=False)}\n\n"
            
            async for chunk in graph.astream(
                input={"messages": [HumanMessage(content=request.message)]},
                config=config,
                subgraphs=True,
                stream_mode=["updates", "custom"],
            ):
                print(chunk)
                # chunk[-1]을 JSON으로 직렬화
                chunk_data = chunk[-1]
                json_str = serialize_chunk(chunk_data)
                yield f"data: {json_str}\n\n"

        except Exception as e:
             yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
            

@app.post("/chat/resume")
async def resume_interrupt(request: ResumeRequest):
    """Interrupt 후 사용자 응답으로 재개"""
    try:
        graph = await get_graph()
        config = {"configurable": {"thread_id": request.thread_id}}

        # 메인 라우터에서 현재 상태 확인
        main_state = await graph.aget_state(config)

        if not main_state.next or len(main_state.next) == 0:
            raise HTTPException(
                status_code=400,
                detail="No interrupt in progress for this thread"
            )

        # 현재 진행 중인 노드 확인
        current_node = main_state.next[0] if main_state.next else None

        print(f"📍 Resume 요청: thread_id={request.thread_id}, current_node={current_node}, user_response={request.user_response}")

        # Interrupt를 재개: resume 값은 interrupt()의 반환값이 됨
        command = Command(
            resume=request.user_response
        )

        async def event_stream():
            """Interrupt 재개 후 스트리밍 응답 생성"""
            try:
                # 스트림 시작 시 thread_id를 클라이언트에 전송
                yield f"data: {json.dumps({'event_type': 'thread_id', 'thread_id': request.thread_id}, ensure_ascii=False)}\n\n"

                # 메인 라우터에 재개 명령 전송
                # 메인 라우터가 checkpoint 관리하므로 메인 라우터를 통해 처리
                async for chunk in graph.astream(
                    command,
                    config,
                    subgraphs=True,
                    stream_mode=["updates", "custom"],
                ):
                    chunk_data = chunk[-1]
                    json_str = serialize_chunk(chunk_data)
                    yield f"data: {json_str}\n\n"

            except Exception as e:
                print(f"❌ Resume 스트림 오류: {str(e)}")
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Resume 에러: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Resume failed: {str(e)}")


@app.get("/chat/status/{thread_id}")
async def get_status(thread_id: str):
    """특정 thread의 현재 상태 확인"""
    try:
        graph = await get_graph()
        config = {"configurable": {"thread_id": thread_id}}
        state = await graph.aget_state(config)

        return {
            "thread_id": thread_id,
            "next": state.next,
            "values": state.values if state.values else {},
            "interrupted": state.next is not None and len(state.next) > 0
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Thread not found: {str(e)}")


if __name__ == '__main__':
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info",
        access_log=False  # 액세스 로그 비활성화로 버퍼링 감소
    )