import { ReactNode, useEffect, useMemo, useState } from "react";
import { 
  AssistantRuntimeProvider, 
  makeAssistantToolUI,
  useAssistantTransportRuntime,
  unstable_createMessageConverter as createMessageConverter,
  AssistantTransportConnectionMetadata
} from "@assistant-ui/react";
import {
  convertLangChainMessages,
  LangChainMessage,
} from "@assistant-ui/react-langgraph"
import { Thread } from "@/components/assistant-ui/thread";
import { DevToolsModal } from "@assistant-ui/react-devtools";
import "./App.css";

const createThread = async (token: string) => {
  const res = await fetch("http://localhost:8000/threads", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    }
  });

  const { thread_id } = await res.json();

  return thread_id;
}

const SelectWorkspaceToolUI = makeAssistantToolUI<
  { workspaceId: string },
  { workspaceId: string }
>({
  toolName: "request_workspace_selection",
  render: ({ args, result, status, addResult, toolCallId, resume }) => {
    const handleSelect = (workspaceId: string) => {
      console.log("Calling addResult:", { 
        workspaceId,
        toolCallId  // 여기서 전달되는 toolCallId
      });
      addResult({ workspaceId });
      // resume({ workspaceId });
    };

    if(result) {
      return (
        <div>
          워크스페이스 선택 완료!
          {result.workspaceId}
        </div>
      )
    }

    return (
      <div>
        <div>{status.type}</div>
        <div>{toolCallId}</div>
        <h1>Select Workspace</h1>
        <div>
          <button onClick={() => handleSelect("123")}>123</button>
        </div>
      </div>
    )
  }
})

type State = {
  messages: LangChainMessage[];
};

const LangChainMessageConverter = createMessageConverter(
  convertLangChainMessages,
);

const converter = (
  state: State,
  connectionMetadata: AssistantTransportConnectionMetadata,
) => {
  const optimisticStateMessages = connectionMetadata.pendingCommands.map(
    (c): LangChainMessage[] => {
      if (c.type === "add-message") {
        return [
          {
            type: "human" as const,
            content: [
              {
                type: "text" as const,
                text: c.message.parts
                  .map((p) => (p.type === "text" ? p.text : ""))
                  .join("\n"),
              },
            ],
          },
        ];
      }

      if (c.type === "add-tool-result") {
        return [
          {
            type: "tool" as const,
            tool_call_id: c.toolCallId,
            content: JSON.stringify(c.result),
            name: c.toolName,
            status: "success" as const,
          }
        ]
      }
      return [];
    },
  );
  
  const messages = [...state.messages, ...optimisticStateMessages.flat()];


  return {
    messages: LangChainMessageConverter.toThreadMessages(messages),
    isRunning: connectionMetadata.isSending || false,
  };
};

function App() {
  const [token, setToken] = useState("");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [inputToken, setInputToken] = useState("");
  const [threadId, setThreadId] = useState<string | null>(null);

  const runtimeOptions = useMemo(() => ({
    initialState: { messages: [] },
    converter: converter,
    api: "http://localhost:8000/assistant",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: {
      threadId: threadId,
    }
  }), [token, threadId])

  const runtime = useAssistantTransportRuntime({
    ...runtimeOptions,
    onResponse: (response) => {
      console.log("response", response);
    },
    onError: (error) => {
      console.error("error", error);
    },
    onFinish: () => {
      console.log("finish");
    },
    onCancel: () => {
      console.log("cancel");
    }
  })

  const handleLogin = () => {
    if (inputToken.trim()) {
      setToken(inputToken.trim());
      setIsAuthenticated(true);
    }
  };

  useEffect(() => {
    if(token && !threadId) {
      createThread(token).then((newThreadId) => {
        setThreadId(newThreadId);
      });
    }
  }, [token, threadId])
  
  if (!isAuthenticated) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <h1>🤖 Agent Chat UI</h1>
          <p>Enter your bearer token to continue</p>
          <input
            type="password"
            placeholder="Bearer Token"
            value={inputToken}
            onChange={(e) => setInputToken(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            className="auth-input"
          />
          <button onClick={handleLogin} className="auth-button">
            Connect
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      <AssistantRuntimeProvider runtime={runtime}>
        <Thread />
        <SelectWorkspaceToolUI/>
        <DevToolsModal />
      </AssistantRuntimeProvider>
    </div>
  );
}

export default App;
