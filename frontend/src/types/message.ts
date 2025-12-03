export interface ChatRequest {
  threadId: string;
  messages: Message[];
}

export type Message = UserMessage | AssistantMessage;

export type ContentPart = 
  | { type: 'text'; text: string }
  | { type: 'image'; image: string }
  | { type: 'tool-call'; toolCallId: string; toolName: string; args: Record<string, any>; result?: any }
  | { type: 'tool-result'; toolCallId: string; toolName: string; result: any };

export interface UserMessage {
  role: 'user';
  content: ContentPart[];
}

export interface AssistantMessage {
  role: 'assistant';
  content: ContentPart[];
}

export interface ToolCall {
  id: string;
  type: 'function';
  function: {
    name: string;
    arguments: string; // JSON string
  };
}

export interface ToolMessage {
  role: 'tool';
  tool_call_id: string;
  content: string;
}

export type StreamEvent = 
  | TextDeltaEvent
  | ToolCallEvent
  | ToolCallDeltaEvent
  | ToolResultEvent
  | FinishEvent
  | ErrorEvent;

export interface TextDeltaEvent {
  type: 'text-delta';
  textDelta: string;
}

export interface ToolCallEvent {
  type: 'tool-call';
  toolCallId: string;
  toolName: string;
  args: Record<string, any>;
}

export interface ToolCallDeltaEvent {
  type: 'tool-call-delta';
  toolCallId: string;
  toolName: string;
  argsTextDelta: string;
}

export interface ToolResultEvent {
  type: 'tool-result';
  toolCallId: string;
  toolName: string;
  result: any;
}

export interface FinishEvent {
  type: 'finish';
  usage?: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
}

export interface ErrorEvent {
  type: 'error';
  error: string;
}