import { useState, useMemo, useRef } from "react";
import {
  AssistantRuntimeProvider,
  useLocalRuntime,
  type ChatModelAdapter,
} from "@assistant-ui/react";
import { Thread } from "@/components/assistant-ui/thread";
import "@assistant-ui/react/styles/index.css";
import "./App.css";

function App() {
  const [token, setToken] = useState("");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [inputToken, setInputToken] = useState("");
  const threadIdRef = useRef<string | null>(null);

  // Create thread helper
  const createThread = async (authToken: string): Promise<string> => {
    const response = await fetch("/threads", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({ metadata: {} }),
    });

    if (!response.ok) {
      throw new Error(`Failed to create thread: ${response.statusText}`);
    }

    const data = await response.json();
    return data.thread_id;
  };

  // Create adapter for assistant-ui that calls backend API directly
  const adapter: ChatModelAdapter = useMemo(
    () => ({
      async *run({ messages, abortSignal }) {
        // Ensure we have a thread
        if (!threadIdRef.current) {
          threadIdRef.current = await createThread(token);
        }

        // Convert messages to backend format
        const backendMessages = messages.map((msg) => ({
          type: msg.role === "user" ? "human" : "ai",
          content:
            typeof msg.content === "string"
              ? msg.content
              : msg.content
                .map((c) => (c.type === "text" ? c.text : ""))
                .join(""),
        }));

        // Stream from backend
        const response = await fetch(
          `/threads/${threadIdRef.current}/runs/stream`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              assistant_id: "default",
              input: {
                messages: backendMessages,
              },
            }),
            signal: abortSignal,
          }
        );

        if (!response.ok) {
          throw new Error(`Failed to run thread: ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error("No response body");
        }

        const decoder = new TextDecoder();
        let buffer = "";
        let fullText = "";

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";

            for (const line of lines) {
              if (!line.trim() || !line.startsWith("data: ")) continue;

              try {
                const data = JSON.parse(line.slice(6));

                // Handle message chunks from backend
                if (data.content && data.type === "ai") {
                  fullText += data.content;

                  // Yield in assistant-ui expected format
                  yield {
                    content: [{ type: "text", text: fullText }],
                  };
                }
              } catch (e) {
                console.error("Failed to parse SSE data:", e);
              }
            }
          }
        } finally {
          reader.releaseLock();
        }
      },
    }),
    [token]
  );

  const runtime = useLocalRuntime(adapter);

  const handleLogin = () => {
    if (inputToken.trim()) {
      setToken(inputToken.trim());
      setIsAuthenticated(true);
    }
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    setToken("");
    setInputToken("");
    threadIdRef.current = null; // Reset thread on logout
  };

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
      <div className="app-header">
        <h2>🤖 Agent Chat UI</h2>
        <button onClick={handleLogout} className="logout-button">
          Logout
        </button>
      </div>
      <AssistantRuntimeProvider runtime={runtime}>
        <div className="thread-container">
          <Thread />
        </div>
      </AssistantRuntimeProvider>
    </div>
  );
}

export default App;
