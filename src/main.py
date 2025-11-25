from datetime import datetime
import json
from fastapi.security import HTTPAuthorizationCredentials
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from typing_extensions import Any, Dict, List
from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn  
from typing import Optional 
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from agents import create_graph
from auth import security, verify_token
from langgraph.types import Command

# 프로젝트 루트를 PYTHONPATH에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

graph = None


app = FastAPI(dependencies=[Depends(verify_token)])


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


class RunCreate(BaseModel):
    assistant_id: str
    input: Optional[Dict[str, Any]] = None
    command: Optional[Dict[str, Any]] = None  # For resume with Command
    stream_mode: Optional[List[str]] = ["messages"]



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
    """assistant-ui가 스레드 전환 시 호출"""
    token = credentials.credentials
    
    try:
        config = {
            "configurable": {
                "thread_id": thread_id,
                "token": token
            }
        }
        
        graph = await create_graph(config=config)
        state = await graph.aget_state(config)
        
        # interrupts 추출
        interrupts = []
        tasks = []
        if hasattr(state, 'tasks'):
            for task in state.tasks:
                task_interrupts = getattr(task, 'interrupts', [])
                tasks.append({
                    "id": getattr(task, 'id', None),
                    "name": getattr(task, 'name', None),
                    "interrupts": [
                        {
                            "value": getattr(i, 'value', i),
                            "resumable": getattr(i, 'resumable', True),
                            "when": getattr(i, 'when', 'during'),
                        }
                        for i in task_interrupts
                    ],
                })
                interrupts.extend(task_interrupts)
        
        # LangChain 메시지를 LangGraph SDK 형식으로 변환
        messages = []
        if hasattr(state, 'values') and 'messages' in state.values:
            for msg in state.values['messages']:
                messages.append(convert_message_to_dict(msg))
        
        return {
            "values": {"messages": messages},
            "next": list(state.next) if hasattr(state, 'next') else [],
            "tasks": tasks,
            "metadata": state.metadata if hasattr(state, 'metadata') else {},
        }
        
    except Exception as e:
        return {
            "values": {"messages": []},
            "next": [],
            "tasks": [],
            "metadata": {},
        }


@app.post("/threads/{thread_id}/runs/stream")
async def stream_run(
    thread_id: str,
    request: RunCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """메인 스트리밍 엔드포인트 - assistant-ui 호환"""
    token = credentials.credentials
    
    async def generate():
        try:
            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "token": token
                }
            }
            
            graph = await create_graph(config=config)
            
            # input 또는 command 결정
            if request.command:
                # Resume from interrupt
                from langgraph.types import Command
                graph_input = Command(**request.command)
            elif request.input:
                graph_input = request.input
            else:
                graph_input = {"messages": []}
            
            # stream_mode 결정
            stream_modes = request.stream_mode or ["messages"]
            
            # "messages" 모드 사용 시 토큰 단위 스트리밍
            if "messages" in stream_modes:
                async for chunk, metadata in graph.astream(
                    graph_input,
                    config=config,
                    stream_mode="messages",
                ):
                    # 메시지 청크 이벤트
                    event_data = {
                        "event": "messages/partial",
                        "data": [convert_message_to_dict(chunk)]
                    }
                    yield f"event: messages/partial\n"
                    yield f"data: {json.dumps(event_data['data'])}\n\n"
            else:
                # updates 모드
                async for chunk in graph.astream(
                    graph_input,
                    config=config,
                    stream_mode="updates",
                ):
                    for node, values in chunk.items():
                        event_data = {
                            "event": "updates",
                            "data": {node: serialize_values(values)}
                        }
                        yield f"event: updates\n"
                        yield f"data: {json.dumps(event_data['data'])}\n\n"
            
            # 스트림 종료 후 상태 확인
            snapshot = await graph.aget_state(config)
            
            # 최종 메시지 상태 전송
            final_messages = []
            if hasattr(snapshot, 'values') and 'messages' in snapshot.values:
                final_messages = [
                    convert_message_to_dict(m) 
                    for m in snapshot.values['messages']
                ]
            
            yield f"event: messages/complete\n"
            yield f"data: {json.dumps(final_messages)}\n\n"
            
            # 인터럽트 확인
            if snapshot.next:
                interrupts = []
                for task in getattr(snapshot, 'tasks', []):
                    for interrupt in getattr(task, 'interrupts', []):
                        interrupts.append({
                            "value": getattr(interrupt, 'value', interrupt),
                            "resumable": getattr(interrupt, 'resumable', True),
                            "when": getattr(interrupt, 'when', 'during'),
                        })
                
                if interrupts:
                    yield f"event: interrupt\n"
                    yield f"data: {json.dumps(interrupts)}\n\n"
            
            # 완료 이벤트
            yield f"event: end\n"
            yield f"data: {json.dumps({'status': 'complete'})}\n\n"
            
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

def convert_message_to_dict(message) -> Dict[str, Any]:
    """LangChain 메시지를 LangGraph SDK 형식으로 변환"""
    if isinstance(message, AIMessage):
        result = {
            "type": "ai",
            "id": getattr(message, 'id', None),
            "content": message.content,
        }
        if hasattr(message, 'tool_calls') and message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.get("id"),
                    "name": tc.get("name"),
                    "args": tc.get("args"),
                }
                for tc in message.tool_calls
            ]
        return result
    
    elif isinstance(message, AIMessageChunk):
        result = {
            "type": "ai",
            "id": getattr(message, 'id', None),
            "content": message.content or "",
        }
        if hasattr(message, 'tool_calls') and message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.get("id"),
                    "name": tc.get("name"),
                    "args": tc.get("args"),
                }
                for tc in message.tool_calls
            ]
        return result
    
    elif isinstance(message, HumanMessage):
        return {
            "type": "human",
            "id": getattr(message, 'id', None),
            "content": message.content,
        }
    
    elif isinstance(message, ToolMessage):
        return {
            "type": "tool",
            "id": getattr(message, 'id', None),
            "content": message.content,
            "tool_call_id": getattr(message, 'tool_call_id', None),
            "name": getattr(message, 'name', None),
        }
    
    else:
        return {
            "type": "unknown",
            "content": str(message),
        }

def serialize_values(values: Any) -> Any:
    if isinstance(values, dict):
        result = {}
        for k, v in values.items():
            if k == "messages":
                result[k] = [convert_message_to_dict(m) for m in v]
            else:
                result[k] = serialize_values(v)
        return result
    elif isinstance(values, list):
        return [serialize_values(item) for item in values]
    elif hasattr(values, '__dict__'):
        return str(values)
    return values

if __name__ == '__main__':
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info",
    )