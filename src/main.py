import json
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from pydantic import BaseModel
from typing_extensions import Optional, List, Any
import uuid
from fastapi.security import HTTPAuthorizationCredentials
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from assistant_stream import RunController, append_langgraph_event, create_run, get_tool_call_subgraph_state
from assistant_stream.serialization import DataStreamResponse
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from interal_types import ChatRequest

load_dotenv()

from graph import create_scrum_agent_graph
from auth import security, verify_token

import uvicorn 

app = FastAPI(dependencies=[Depends(verify_token)])

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", dependencies=[])
def health_check():
    return {"status": "ok"}

@app.post("/threads")
def create_thread(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return {"thread_id": str(uuid.uuid4())}

@app.post("/assistant")
async def chat_endpoint(
    request: ChatRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    async def run(controller: RunController):
        token = credentials.credentials
        if not token:
            raise HTTPException(status_code=401, detail="Unauthorized")

        config = {
          "configurable": {
            "thread_id": request.threadId,
            "token": token
          }
        }

        try:
          graph = await create_scrum_agent_graph(config)
        except Exception as e:
          raise HTTPException(status_code=500, detail=str(e))

        if controller.state is None:
            controller.state = {}
        if "messages" not in controller.state:
            controller.state["messages"] = []
    
        input_messages = []
        is_tool_result = False
        tool_result = None

        for command in request.commands:
            if command.type == "add-message":
                text_parts = [
                    part.text for part in command.message.parts
                    if part.type == "text" and part.text
                ]
                if text_parts:
                    input_messages.append(HumanMessage(content=" ".join(text_parts)))

            elif command.type == "add-tool-result":
                is_tool_result = True
                
                tool_result = command.result

                input_messages.append(ToolMessage(
                    content=str(command.result),
                    tool_call_id=command.toolCallId,
                    name=command.toolName
                ))

        for message in input_messages:
            controller.state["messages"].append(message.model_dump())

        snapshot = graph.get_state(config)
        run_input = None

        if snapshot.next and is_tool_result:
            run_input = Command(resume=tool_result)

        else:
            run_input = {"messages": input_messages}

        async for namespace, event_type, chunk in graph.astream(
            run_input,
            config,
            stream_mode=["messages", "updates"],
            subgraphs=True
        ):
            if event_type == "messages":
                msg, metadata = chunk

                if isinstance(msg, (AIMessage, AIMessageChunk)):
                    if not msg.content and not msg.tool_calls:
                        continue
                
            state = get_tool_call_subgraph_state(
                controller,
                subgraph_node="tools",
                namespace=namespace,
                artifact_field_name="subgraph_state",
                default_state={}
            )

            append_langgraph_event(
                state,
                namespace,
                event_type,
                chunk
            )

    return DataStreamResponse(create_run(run, state=request.state))

if __name__ == '__main__':
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info",
    )