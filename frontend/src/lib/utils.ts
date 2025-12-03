import { ThreadMessage } from "@assistant-ui/react"
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import type { Message } from "@/types/message"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Convert ThreadMessage to Message format
 * @param messages 
 * @returns Message[]
 */
export const convertMessages = (messages: readonly ThreadMessage[]): Message[] => {
  return messages.map(msg => {
    if (msg.role === 'user') {
      const textParts = msg.content
        .filter((c): c is Extract<typeof c, { type: 'text' }> => c.type === 'text')
        .map(c => ({ type: 'text' as const, text: c.text }));
      
      return {
        role: 'user' as const,
        content: textParts.length > 0 ? textParts : [{ type: 'text' as const, text: '' }]
      } satisfies Message;
    } else {
      const assistantMsg = msg as Extract<ThreadMessage, { role: 'assistant' }>;
      const textParts = assistantMsg.content
        .filter((c): c is Extract<typeof c, { type: 'text' }> => c.type === 'text')
        .map(c => ({ type: 'text' as const, text: c.text }));
      
      const toolCalls = assistantMsg.content
        .filter((c): c is Extract<typeof c, { type: 'tool-call' }> => c.type === 'tool-call')
        .map(c => ({
          type: 'tool-call' as const,
          toolCallId: c.toolCallId,
          toolName: c.toolName,
          args: c.args,
          ...(c.result !== undefined ? { result: c.result } : {}),
        }));
      
      return {
        role: 'assistant' as const,
        content: [
          ...textParts,
          ...toolCalls,
        ]
      } satisfies Message;
    }
  });
}

/**
 * Read DataStream format and yield data
 * DataStream format: prefix:data\n
 * - 0:{text} - text-delta (simple string)
 * - aui-text-delta:{json} - text-delta with parent_id
 * - b:{json} - tool-call-begin
 * - c:{json} - tool-call-delta
 * - a:{json} - tool-result
 * - 3:{json} - error
 * - aui-state:{json} - state update
 * @param response 
 */
export async function* readSSEStream(response: Response) {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();

  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.trim()) continue;
        
        try {
          const colonIndex = line.indexOf(':');
          if (colonIndex === -1) continue;

          const prefix = line.slice(0, colonIndex);
          const dataStr = line.slice(colonIndex + 1);

          let event: any;

          // Parse based on prefix
          if (prefix === '0') {
            // Simple text-delta (just a string)
            event = {
              type: 'text-delta',
              textDelta: JSON.parse(dataStr)
            };
          } else if (prefix === 'aui-text-delta') {
            // Text-delta with parent_id
            const data = JSON.parse(dataStr);
            event = {
              type: 'text-delta',
              textDelta: data.textDelta,
              parentId: data.parentId
            };
          } else if (prefix === 'b') {
            // Tool-call-begin
            const data = JSON.parse(dataStr);
            event = {
              type: 'tool-call',
              toolCallId: data.toolCallId,
              toolName: data.toolName,
              parentId: data.parentId
            };
          } else if (prefix === 'c') {
            // Tool-call-delta
            const data = JSON.parse(dataStr);
            event = {
              type: 'tool-call-delta',
              toolCallId: data.toolCallId,
              argsTextDelta: data.argsTextDelta
            };
          } else if (prefix === 'a') {
            // Tool-result
            const data = JSON.parse(dataStr);
            event = {
              type: 'tool-result',
              toolCallId: data.toolCallId,
              result: data.result,
              artifact: data.artifact,
              isError: data.isError
            };
          } else if (prefix === '3') {
            // Error
            event = {
              type: 'error',
              error: JSON.parse(dataStr)
            };
          } else if (prefix === 'aui-state') {
            // State update - skip for now
            continue;
          } else {
            // Unknown prefix, skip
            console.warn('Unknown DataStream prefix:', prefix);
            continue;
          }

          yield event;
        } catch (e) {
          console.error('Failed to parse DataStream line:', line, e);
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}