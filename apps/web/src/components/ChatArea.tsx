import { useCallback, useEffect, useState } from "react";
import { ChatInput } from "./ChatInput";
import { CategoryPills } from "./CategoryPills";
import { EndpointActions, type EndpointAction } from "./EndpointActions";
import { api } from "@/lib/api";
import { useAttachments } from "@/hooks/useAttachments";
import type { ChatAttachment, ChatMessage, ChatThread, StepInfo } from "@/types/chat";

interface ChatAreaProps {
  activeThread?: ChatThread;
  addMessage: (message: Omit<ChatMessage, "id" | "createdAt">) => void;
  setAssistantPlaceholder: () => void;
  replaceLastAssistantMessage: (content: string, steps?: StepInfo[]) => void;
}

export const ChatArea = ({
  activeThread,
  addMessage,
  setAssistantPlaceholder,
  replaceLastAssistantMessage,
}: ChatAreaProps) => {
  const [inputValue, setInputValue] = useState("");
  const [sending, setSending] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const { attachments, addFiles, removeAttachment, reset } = useAttachments();

  useEffect(() => {
    // Clean attachments when switching threads (only when thread ID changes)
    reset();
  }, [activeThread?.id, reset]);

  const handleSubmit = async (attached: ChatAttachment[]) => {
    if ((!inputValue.trim() && attached.length === 0) || !activeThread) return;

    const userMessage: Omit<ChatMessage, "id" | "createdAt"> = {
      role: "user",
      content: inputValue,
      attachments: attached,
    };

    addMessage(userMessage);
    setInputValue("");
    reset();
    setSending(true);

    setAssistantPlaceholder();

    try {
      const uploadedFilename = attached[0]?.uploadedFilename;
      const res = await api.chat(userMessage.content, uploadedFilename);
      replaceLastAssistantMessage(res.response || "Done.", res.steps);
    } catch (err: any) {
      replaceLastAssistantMessage(err?.message || "Failed to get response");
    } finally {
      setSending(false);
    }
  };

  const isEmptyState = !activeThread || activeThread.messages.length === 0;
  const conversation = activeThread?.messages ?? [];

  const handleAddFiles = useCallback((files: FileList | File[]) => {
    addFiles(files);
  }, [addFiles]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleAddFiles(files);
    }
  }, [handleAddFiles]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.types.includes("Files")) {
      setIsDragging(true);
    }
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    // Only set to false if we're leaving the ChatArea entirely
    if (e.currentTarget === e.target) {
      setIsDragging(false);
    }
  }, []);

  const apiActions: EndpointAction[] = [
    { id: "tabs-list", label: "List tabs", category: "browser-tabs", onRun: () => api.tabsList() },
    { id: "tabs-organize", label: "Organize tabs", category: "browser-tabs", onRun: () => api.tabsOrganize() },
    { id: "tabs-close", label: "Close old tabs", category: "browser-tabs", onRun: () => api.tabsCloseOld(7) },
    { id: "tabs-merge", label: "Merge duplicates", category: "browser-tabs", onRun: () => api.tabsMergeDuplicates() },
    { id: "tabs-sessions", label: "List tab sessions", category: "browser-tabs", onRun: () => api.tabsSessions() },
    { id: "jobs-portals", label: "Job portals", category: "jobs", onRun: () => api.jobPortals() },
    { id: "applications-sheets", label: "Google Sheets apps", category: "jobs", onRun: () => api.applicationsSheets() },
    { id: "health", label: "Gateway health", category: "misc", onRun: () => api.health() },
    { id: "wallpaper-search", label: "Search wallpaper", category: "misc", onRun: () => api.searchWallpaper() },
    { id: "daily-login-duolingo", label: "Daily login (Duolingo)", category: "misc", onRun: () => api.dailyLogin("Duolingo") },
  ];

  const handleActionResult = (label: string, result: any) => {
    // Extract steps if present
    const steps = result?.steps || [];
    
    // If we have steps, show a cleaner message
    let content: string;
    if (steps.length > 0) {
      // Show just the high-level status, steps will be displayed separately
      const status = result?.success ? "✓ Success" : "✗ Failed";
      const message = result?.message || result?.error || "";
      content = `${label}: ${status}${message ? ` - ${message}` : ""}`;
    } else {
      // No steps, show full JSON (legacy behavior)
      content = `${label}:\n${JSON.stringify(result, null, 2)}`;
    }
    
    addMessage({ 
      role: "assistant", 
      content,
      steps: steps.length > 0 ? steps : undefined,
    });
  };

  return (
    <div
      className="flex-1 flex flex-col h-screen bg-chat overflow-hidden relative"
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
    >
      {/* Drag overlay */}
      {isDragging && (
        <div className="absolute inset-0 bg-primary/10 backdrop-blur-sm border-4 border-dashed border-primary z-50 flex items-center justify-center">
          <div className="text-center">
            <p className="text-2xl font-semibold text-primary">Drop files here</p>
            <p className="text-sm text-muted-foreground mt-2">Upload images or PDFs</p>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        {isEmptyState ? (
          <div className="flex flex-col items-center justify-center min-h-full px-4 py-12 space-y-6 text-center">
            <h1 className="text-3xl md:text-4xl font-semibold text-foreground mb-2 fade-in">How can I help you?</h1>
            <div className="w-full">
              <CategoryPills activeCategory={activeCategory} onSelect={(cat) => setActiveCategory(activeCategory === cat ? null : cat)} />
              <div className="mt-6">
                <EndpointActions actions={apiActions} activeCategory={activeCategory} onResult={handleActionResult} />
              </div>
            </div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto px-4 py-8 space-y-4">
            {conversation.map((message) => (
              <div key={message.id} className={`fade-in ${message.role === "user" ? "text-right" : "text-left"}`}>
                <div
                  className={`inline-block max-w-[85%] px-4 py-3 rounded-2xl ${message.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary text-secondary-foreground"
                    }`}
                >
                  <div className="space-y-2">
                    {message.attachments?.length ? (
                      <div className="flex gap-3 flex-wrap items-start">
                        {message.attachments.map((att) => {
                          const isImage = att.kind === "image" && att.previewUrl;
                          return (
                            <div key={att.id} className="relative">
                              <div className={`flex items-center gap-3 rounded-2xl border border-border/70 bg-card/90 shadow-sm px-3 py-2 ${isImage ? "pr-5" : "pr-10"}`}>
                                {isImage ? (
                                  <img src={att.previewUrl} alt={att.name} className="h-16 w-16 rounded-xl object-cover" />
                                ) : (
                                  <div className="h-14 w-14 rounded-xl bg-red-500/90 flex items-center justify-center text-white text-xs font-semibold">
                                    PDF
                                  </div>
                                )}
                                <div className="max-w-[200px]">
                                  <p className="text-sm font-semibold text-foreground truncate">{att.name}</p>
                                  <p className="text-xs text-muted-foreground uppercase">{att.kind}</p>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : null}
                    <div>{message.content}</div>
                    {message.role === "assistant" && message.steps && message.steps.length > 0 && (
                      <div className="mt-3 space-y-1 border-l-2 border-primary/30 pl-3">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">Steps</p>
                        {message.steps.map((step, i) => (
                          <div key={i} className="text-sm text-muted-foreground">
                            <span className="font-medium text-foreground/80">Step {step.step_number}/{step.total_steps}:</span>{" "}
                            {step.description}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="p-4 pb-6">
        <ChatInput
          value={inputValue}
          onChange={setInputValue}
          onSubmit={handleSubmit}
          attachments={attachments}
          onRemoveAttachment={removeAttachment}
          onAddFiles={handleAddFiles}
        />
      </div>
    </div>
  );
};
