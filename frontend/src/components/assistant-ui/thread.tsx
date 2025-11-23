"use client";

import { Thread as AssistantThread } from "@assistant-ui/react";
import { makeMarkdownText } from "@assistant-ui/react-markdown";

const MarkdownText = makeMarkdownText();

export function Thread() {
  return (
    <AssistantThread
      welcome={{
        message: "안녕하세요! 무엇을 도와드릴까요?",
      }}
      assistantMessage={{
        components: {
          Text: MarkdownText,
        },
      }}
    />
  );
}
