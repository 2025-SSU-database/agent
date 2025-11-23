from datetime import datetime
import json
from fastapi.security import HTTPAuthorizationCredentials
from langchain_core.messages import BaseMessage, AIMessage, AIMessageChunk, HumanMessage
from typing_extensions import Any, Dict
from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn  
from typing import Optional 
from contextlib import asynccontextmanager
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from agents import create_graph
from auth import security, verify_token

# 프로젝트 루트를 PYTHONPATH에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

graph = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph

    print("Creating graph...")
    graph = await create_graph()
    print("Graph created")
    yield
    print("Bye")

app = FastAPI(dependencies=[Depends(verify_token)], lifespan=lifespan)

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

class ThreadCreate(BaseModel):
    metadata: Optional[Dict[str, Any]] = {}

class RunRequest(BaseModel):
    assistant_id: str
    input: Dict[str, Any]

class ResumeRequest(BaseModel):
    thread_id: str
    # HITL 스타일 결정
    decisions: Optional[list[dict]] = None  # [{"type": "approve|edit|reject", ...}]
    # 레거시 지원
    approved: Optional[bool] = None  # 사용자 승인 여부
    user_response: Optional[str] = None  # 사용자 응답 (추가 정보 제공 시)
    workspace_id: Optional[str] = None  # Workspace ID (현재 워크스페이스)

@app.get("/health", dependencies=[])
def health_check():
    return {"status": "ok"}

@app.post("/threads")
async def create_thread(request: ThreadCreate = ThreadCreate()):
    from uuid import uuid4

    thread_id = str(uuid4())
    
    return {
        "thread_id": thread_id,
        "created_at": datetime.now().isoformat(),
        "metadata": request.metadata
    }

@app.get("/threads/{thread_id}/state")
async def get_thread_state(
    thread_id: str, 
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    try:
        config = {
            "configurable": {
                "thread_id": thread_id,
                "token": token
            }
        }
        state = await graph.ainvoke(config=config)

        tasks = []
        if hasattr(state, 'tasks'):
            for task in state.tasks:
                tasks.append({
                    "id": getattr(task, 'id', None),
                    "name": getattr(task, 'name', None),
                    "interrupts": getattr(task, 'interrupts', []),
                })
        
        return {
            "values": state.values if hasattr(state, 'values') else {},
            "next": state.next if hasattr(state, 'next') else [],
            "tasks": tasks,
            "metadata": state.metadata if hasattr(state, 'metadata') else {},
        }
        
    except Exception as e:
        # 스레드가 없는 경우 빈 상태 반환
        return {
            "values": {"messages": []},
            "next": [],
            "tasks": [],
            "metadata": {},
        }

@app.post("/threads/{thread_id}/runs/stream")
async def stream_run(
    thread_id: str, 
    request: RunRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    
    async def generate():
        try:
            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "token": token
                }
            }
            
            # 입력 메시지 추가
            input_messages = request.input.get("messages", [])
            
            # LangGraph 스트리밍 실행 - messages 모드로 메시지만 스트리밍
            async for namespace, chunk in graph.astream(
                {
                    "messages": input_messages
                },
                config=config,
                stream_mode="updates",
                subgraphs=True
            ):
                for node, values in chunk.items():
                     # Check for messages in the node output
                    if isinstance(values, dict) and "messages" in values:
                        for message in values["messages"]:
                            if isinstance(message, (AIMessage, AIMessageChunk)):
                                content = message.content
                                if content:
                                    chunk_data = {
                                        "content": content,
                                        "type": "ai"
                                    }
                                    yield f"data: {json.dumps(chunk_data)}\n\n"
                            elif isinstance(message, HumanMessage):
                                 # We usually don't need to stream back human messages, but handled if needed
                                 pass

        except Exception as e:
            yield f"event: error\n"
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

@app.post("/threads/{thread_id}/runs/{run_id}/resume")
async def resume_run(
    thread_id: str, 
    run_id: str,
    resume_data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    
    """인터럽트된 실행 재개"""
    
    config = {"configurable": {"thread_id": thread_id, "token": token}}
    
    # 인터럽트에 대한 응답 전달
    result = await graph.ainvoke(
        resume_data,
        config=config
    )
    
    return {
        "status": "resumed",
        "thread_id": thread_id,
        "run_id": run_id,
    }

if __name__ == '__main__':
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info",
        access_log=False  # 액세스 로그 비활성화로 버퍼링 감소
    )