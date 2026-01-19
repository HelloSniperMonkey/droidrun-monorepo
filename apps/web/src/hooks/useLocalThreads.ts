import { useEffect, useState } from "react";
import { loadThreads, saveThreads } from "@/lib/storage";
import type { ChatThread, ChatMessage, ChatAttachment } from "@/types/chat";

const createEmptyThread = (): ChatThread => ({
  id: crypto.randomUUID(),
  title: "New chat",
  messages: [],
  updatedAt: Date.now(),
});

export function useLocalThreads() {
  const [threads, setThreads] = useState<ChatThread[]>(() => {
    const stored = loadThreads();
    if (stored.length) return stored;
    return [createEmptyThread()];
  });

  const [activeThreadId, setActiveThreadId] = useState<string>(() => threads[0]?.id ?? "");

  useEffect(() => {
    saveThreads(threads);
  }, [threads]);

  const activeThread = threads.find((t) => t.id === activeThreadId) ?? threads[0];

  const updateActiveThread = (updater: (thread: ChatThread) => ChatThread) => {
    if (!activeThread) return;
    setThreads((prev) => prev.map((t) => (t.id === activeThread.id ? updater(t) : t)));
  };

  const addMessage = (message: Omit<ChatMessage, "id" | "createdAt">) => {
    if (!activeThread) return;
    const newMsg: ChatMessage = {
      id: crypto.randomUUID(),
      createdAt: Date.now(),
      ...message,
    };
    updateActiveThread((thread) => ({
      ...thread,
      messages: [...thread.messages, newMsg],
      updatedAt: Date.now(),
      title:
        thread.messages.length === 0 && message.role === "user"
          ? newMsg.content.slice(0, 40) || "New chat"
          : thread.title,
    }));
  };

  const replaceLastAssistantMessage = (content: string) => {
    if (!activeThread) return;
    updateActiveThread((thread) => {
      const lastIndex = [...thread.messages].reverse().findIndex((m) => m.role === "assistant");
      if (lastIndex === -1) return thread;
      const realIndex = thread.messages.length - 1 - lastIndex;
      const updated = [...thread.messages];
      updated[realIndex] = { ...updated[realIndex], content, createdAt: Date.now() };
      return { ...thread, messages: updated, updatedAt: Date.now() };
    });
  };

  const setAssistantPlaceholder = () => {
    if (!activeThread) return;
    updateActiveThread((thread) => ({
      ...thread,
      messages: [
        ...thread.messages,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "…",
          createdAt: Date.now(),
        },
      ],
      updatedAt: Date.now(),
    }));
  };

  const addAttachmentToDraft = (attachment: ChatAttachment) => {
    if (!activeThread) return;
    updateActiveThread((thread) => ({
      ...thread,
      draftAttachments: [...(thread.draftAttachments ?? []), attachment],
    }));
  };

  const removeAttachmentFromDraft = (id: string) => {
    if (!activeThread) return;
    updateActiveThread((thread) => ({
      ...thread,
      draftAttachments: (thread.draftAttachments ?? []).filter((a) => a.id !== id),
    }));
  };

  const startNewThread = () => {
    const newThread = createEmptyThread();
    setThreads((prev) => [newThread, ...prev]);
    setActiveThreadId(newThread.id);
  };

  const setActiveById = (id: string) => {
    setActiveThreadId(id);
  };

  return {
    threads,
    activeThread,
    activeThreadId,
    setActiveById,
    addMessage,
    setAssistantPlaceholder,
    replaceLastAssistantMessage,
    addAttachmentToDraft,
    removeAttachmentFromDraft,
    startNewThread,
    setThreads,
  };
}
