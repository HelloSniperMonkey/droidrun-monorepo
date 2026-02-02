import { useCallback, useEffect, useRef, useState } from "react";
import { ChatInput } from "./ChatInput";
import { CategoryPills } from "./CategoryPills";
import { EndpointActions, type EndpointAction } from "./EndpointActions";
import { api } from "@/lib/api";
import { useAttachments } from "@/hooks/useAttachments";
import { useDevice } from "@/contexts/DeviceContext";
import { Plus, Box } from "lucide-react";
import type { ChatAttachment, ChatMessage, ChatThread, StepInfo } from "@/types/chat";

interface ChatAreaProps {
  activeThread?: ChatThread;
  addMessage: (message: Omit<ChatMessage, "id" | "createdAt">) => void;
  setAssistantPlaceholder: () => void;
  replaceLastAssistantMessage: (content: string, steps?: StepInfo[]) => void;
  mode?: "local" | "cloud";
}

export const ChatArea = ({
  activeThread,
  addMessage,
  setAssistantPlaceholder,
  replaceLastAssistantMessage,
  mode,
}: ChatAreaProps) => {
  const [inputValue, setInputValue] = useState("");
  const [sending, setSending] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [llmModel, setLlmModel] = useState("google/gemini-2.5-flash");
  const { attachments, addFiles, removeAttachment, reset } = useAttachments();
  const { selectedDevice } = useDevice();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback((instant = false) => {
    // Use requestAnimationFrame to ensure DOM is rendered before scrolling
    requestAnimationFrame(() => {
      if (scrollContainerRef.current) {
        scrollContainerRef.current.scrollTo({
          top: scrollContainerRef.current.scrollHeight,
          behavior: instant ? "instant" : "smooth"
        });
      }
    });
  }, []);

  // When thread changes, reset scroll to top first, then scroll to messages
  useEffect(() => {
    if (scrollContainerRef.current) {
      // Reset scroll position immediately when switching threads
      scrollContainerRef.current.scrollTop = 0;
    }
    // Then scroll to bottom after a short delay to allow content to render
    const timer = setTimeout(() => scrollToBottom(true), 50);
    return () => clearTimeout(timer);
  }, [activeThread?.id, scrollToBottom]);

  // Scroll to bottom when messages change
  useEffect(() => {
    scrollToBottom();
  }, [activeThread?.messages?.length, scrollToBottom]);

  useEffect(() => {
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
      
      // Use the direct cloud endpoint when in cloud mode to avoid Google GenAI client issues
      if (mode === "cloud") {
        // Start the task (returns immediately with task_id)
        const res = await api.chatCloud(userMessage.content, llmModel, {
          deviceId: selectedDevice?.id,
        });
        
        if (!res.success || !res.task_id) {
          replaceLastAssistantMessage(res.error || res.message || "Cloud task failed to start");
          return;
        }

        const taskId = res.task_id;
        replaceLastAssistantMessage(`🚀 Task started... Waiting for steps...`, []);

        // Poll for live step updates
        let lastStepCount = 0;
        const pollInterval = 1500; // 1.5 seconds
        const maxPolls = 200; // Max ~5 minutes of polling
        let pollCount = 0;

        const poll = async (): Promise<void> => {
          try {
            const statusRes = await api.chatCloudTasks(taskId);
            
            // Convert cloud steps to the expected format
            const formattedSteps = statusRes.steps?.map((step) => ({
              step_number: step.step_number,
              total_steps: statusRes.total_steps || statusRes.steps.length,
              description: step.description || step.event,
              action: step.action,
            })) || [];

            // Update UI with current steps
            if (formattedSteps.length > lastStepCount || statusRes.status !== "running") {
              lastStepCount = formattedSteps.length;
              const statusEmoji = statusRes.status === "completed" ? "✅" : 
                                  statusRes.status === "failed" ? "❌" : "🔄";
              const statusMessage = statusRes.final_answer || 
                                    `${statusEmoji} ${statusRes.status}... (${formattedSteps.length} steps)`;
              replaceLastAssistantMessage(statusMessage, formattedSteps);
            }

            // Check if task is complete
            if (statusRes.status === "completed" || statusRes.status === "failed" || statusRes.status === "cancelled") {
              const finalMessage = statusRes.final_answer || 
                                   (statusRes.status === "completed" ? "Task completed successfully!" : 
                                    statusRes.status === "failed" ? "Task failed." : "Task cancelled.");
              replaceLastAssistantMessage(finalMessage, formattedSteps);
              return; // Stop polling
            }

            // Continue polling
            pollCount++;
            if (pollCount < maxPolls) {
              await new Promise(resolve => setTimeout(resolve, pollInterval));
              return poll();
            } else {
              replaceLastAssistantMessage("⚠️ Polling timeout reached. Task may still be running.", formattedSteps);
            }
          } catch (pollError: any) {
            replaceLastAssistantMessage(`Polling error: ${pollError?.message || "Unknown error"}`, []);
          }
        };

        await poll();
      } else {
        const res = await api.chat(userMessage.content, uploadedFilename, llmModel, mode);
        replaceLastAssistantMessage(res.response || "Done.", res.steps);
      }
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
    if (files.length > 0) handleAddFiles(files);
  }, [handleAddFiles]);

  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); e.stopPropagation(); };
  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.types.includes("Files")) setIsDragging(true);
  };
  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.currentTarget === e.target) setIsDragging(false);
  };

  const apiActions: EndpointAction[] = [
    {
      id: "check-android-version",
      label: <span>Check Android version</span>,
      labelText: "Check Android version",
      category: "misc",
      onRun: async () => {
        handleTaskWithPolling("Check Android Version", api.checkAndroidVersion);
        return {};
      }
    },
    { id: "tabs-list", label: <span>List tabs</span>, labelText: "List tabs", category: "browser-tabs", onRun: () => api.tabsList() },
    { id: "tabs-organize", label: <span>Organize tabs</span>, labelText: "Organize tabs", category: "browser-tabs", onRun: () => api.tabsOrganize() },
    { id: "tabs-close", label: <span>Close old tabs</span>, labelText: "Close old tabs", category: "browser-tabs", onRun: () => api.tabsCloseOld(7) },
    { id: "tabs-merge", label: <span>Merge duplicates</span>, labelText: "Merge duplicates", category: "browser-tabs", onRun: () => api.tabsMergeDuplicates() },
    { id: "tabs-sessions", label: <span>List tab sessions</span>, labelText: "List tab sessions", category: "browser-tabs", onRun: () => api.tabsSessions() },
    { id: "jobs-portals", label: <span>Job portals</span>, labelText: "Job portals", category: "jobs", onRun: () => api.jobPortals() },
    {
      id: "applications-sheets",
      label: <span>Google Sheets apps</span>,
      labelText: "Google Sheets apps",
      category: "jobs",
      onRun: () => {
        window.open("https://docs.google.com/spreadsheets/d/1FupoVr33rLLIOtRrlYxFjXvlMqules-_49pVJcrdgx4/edit", "_blank");
        return Promise.resolve({ success: true, message: "Opened Google Sheets" });
      }
    },
    { id: "health", label: <span>Gateway health</span>, labelText: "Gateway health", category: "misc", onRun: () => api.health() },
  ];

  const handleActionResult = (label: string, result: any) => {
    if (!result || Object.keys(result).length === 0) return;
    const steps = result?.steps || [];
    let content = steps.length > 0
      ? `${label}: ${result?.success ? "Success" : "Failed"}${result?.message ? ` - ${result.message}` : ""}`
      : `${label}:\n${JSON.stringify(result, null, 2)}`;
    replaceLastAssistantMessage(content, steps.length > 0 ? steps : undefined);
  };

  const handleActionStart = (action: EndpointAction) => {
    addMessage({ role: "user", content: action.labelText });
    setAssistantPlaceholder();
  };

  const handleTaskWithPolling = async (label: string, startTask: () => Promise<any>) => {
    try {
      const initialResult = await startTask();
      const taskId = initialResult?.task_id;
      if (!taskId) { handleActionResult(label, initialResult); return; }
      replaceLastAssistantMessage(`${label}: Running... (Task ID: ${taskId})`);
      let attempts = 0, lastStepCount = 0;
      const poll = async () => {
        attempts++;
        try {
          const status = await api.tabsStatus(taskId) as any;
          const currentSteps = status.steps || [];
          if (currentSteps.length > lastStepCount) {
            lastStepCount = currentSteps.length;
            replaceLastAssistantMessage(`${label}: Running... (${currentSteps.length} steps)`, currentSteps);
          }
          if (status.status === "completed" || status.status === "failed") {
            replaceLastAssistantMessage(`${label}: ${status.success ? "Success" : "Completed"} - ${status.message || ""}`, status.steps || []);
            return;
          }
          if (attempts < 60) setTimeout(poll, 2000);
        } catch { if (attempts < 60) setTimeout(poll, 2000); }
      };
      setTimeout(poll, 2000);
    } catch { replaceLastAssistantMessage(`${label}: Task started.`); }
  };

  return (
    <div
      className="flex-1 flex flex-col h-screen bg-background relative overflow-hidden grain"
      onDrop={handleDrop} onDragOver={handleDragOver} onDragEnter={handleDragEnter} onDragLeave={handleDragLeave}
    >
      <div className="absolute inset-0 mesh-gradient z-0" />

      {isDragging && (
        <div className="absolute inset-0 bg-brand-pink/5 backdrop-blur-xl border-2 border-dashed border-brand-pink/20 z-50 flex items-center justify-center animate-in fade-in duration-300">
          <div className="text-center p-8 rounded-3xl bg-card border border-white/5 shadow-2xl">
            <Plus className="h-12 w-12 text-brand-pink mx-auto mb-4 animate-bounce" />
            <p className="text-2xl font-black text-white uppercase">Drop to Upload</p>
          </div>
        </div>
      )}

      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto relative z-10 custom-scrollbar">
        {isEmptyState ? (
          <div className="flex flex-col items-center justify-center min-h-full px-8 py-24 max-w-4xl mx-auto space-y-12">
            <div className="text-center space-y-6 relative z-10">
              <div className="absolute inset-0 bg-brand-pink/20 blur-[100px] rounded-full opacity-20 pointer-events-none" />
              <h1 className="text-5xl md:text-7xl font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-b from-white to-white/60 mb-8 uppercase text-center drop-shadow-2xl relative">
                How can I help you,<br />
                <span className="bg-clip-text text-transparent bg-gradient-to-r from-brand-pink via-purple-500 to-brand-cyan animate-gradient-x bg-[length:200%_auto]">Iron Claw?</span>
              </h1>
              <p className="text-white/40 font-bold max-w-lg mx-auto uppercase tracking-[0.2em] text-xs glass-panel px-4 py-2 rounded-full border border-white/5 inline-block">
                Neural Protocol V2.5 Active & Synced
              </p>
            </div>

            <div className="w-full space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-1000">
              <div className="flex justify-center">
                <div className="bg-white/[0.03] p-1 rounded-2xl border border-white/5 flex gap-1">
                  <CategoryPills activeCategory={activeCategory} onSelect={(cat) => setActiveCategory(activeCategory === cat ? null : cat)} />
                </div>
              </div>

              <div className="min-h-[160px]">
                <EndpointActions actions={apiActions} activeCategory={activeCategory} onResult={handleActionResult} onStart={handleActionStart} />
              </div>
            </div>
          </div>
        ) : (
          <div className="min-h-full flex flex-col justify-end">
            <div className="max-w-3xl mx-auto px-6 py-12 space-y-8 w-full">
              {conversation.map((message, i) => (
                <div
                  key={message.id}
                  className={`flex ${message.role === "user" ? "justify-end" : "justify-start"} animate-in fade-in slide-in-from-bottom-4 duration-500 fill-mode-both`}
                  style={{ animationDelay: `${i * 100}ms` }}
                >
                  <div className={`relative group max-w-[95%] transition-all duration-300 ${message.role === "user" ? "px-5 py-3 rounded-2xl bg-brand-pink text-white font-bold shadow-lg shadow-brand-pink/10" : "w-full"}`}>
                    {message.role === "assistant" && (
                      <div className="flex items-center gap-3 mb-4">
                        <div className="w-6 h-6 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center">
                          <div className="w-1.5 h-1.5 rounded-full bg-brand-pink" />
                        </div>
                        <span className="text-[10px] font-black uppercase tracking-widest text-white/40">Iron Claw</span>
                      </div>
                    )}

                    <div className={`space-y-4 ${message.role === 'assistant' ? 'pl-9' : ''}`}>
                      {message.attachments && message.attachments.length > 0 && (
                        <div className="flex flex-wrap gap-2">
                          {message.attachments.map((att) => (
                            <div key={att.id} className="relative group/att">
                              {att.previewUrl ? <img src={att.previewUrl} alt={att.name} className="w-40 h-28 object-cover rounded-xl border border-white/5" /> : (
                                <div className="px-3 py-2 bg-white/5 rounded-xl flex items-center gap-2 border border-white/5">
                                  <Box className="h-3 w-3 text-white/40" />
                                  <span className="text-[9px] uppercase font-bold tracking-widest text-white/60">{att.name}</span>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                      <div className="text-sm md:text-base leading-relaxed text-white">
                        {message.content === "…" ? (
                          <div className="flex gap-2 items-center py-2 min-h-[1.5rem]">
                            <div className="w-3 h-3 bg-brand-pink rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                            <div className="w-3 h-3 bg-brand-pink rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                            <div className="w-3 h-3 bg-brand-pink rounded-full animate-bounce"></div>
                          </div>
                        ) : (
                          message.content
                        )}
                      </div>
                      {message.role === "assistant" && message.steps && message.steps.length > 0 && (
                        <div className="mt-6 space-y-3">
                          {message.steps.map((step, idx) => (
                            <div key={idx} className="flex gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/5 hover:bg-white/[0.04] transition-all group/step">
                              <div className="flex-shrink-0 w-5 h-5 rounded-md bg-black border border-white/10 flex items-center justify-center text-[9px] font-mono font-bold text-brand-pink">{step.step_number}</div>
                              <div className="flex-1 text-xs font-medium text-white/50 group-hover/step:text-white transition-colors">{step.description}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          </div>
        )}
      </div>

      <div className="p-8 pb-10 relative z-20">
        <div className="max-w-4xl mx-auto">
          <ChatInput value={inputValue} onChange={setInputValue} onSubmit={handleSubmit} attachments={attachments} onRemoveAttachment={removeAttachment} onAddFiles={handleAddFiles} llmModel={llmModel} onLlmModelChange={setLlmModel} />
        </div>
      </div>
    </div>
  );
};
