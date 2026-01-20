import { useState, useEffect } from "react";
import { Sidebar } from "@/components/Sidebar";
import { ChatArea } from "@/components/ChatArea";
import { useLocalThreads } from "@/hooks/useLocalThreads";

const Index = () => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mode, setMode] = useState<"local" | "cloud">("local");
  const {
    threads,
    activeThread,
    activeThreadId,
    setActiveById,
    startNewThread,
    deleteThread,
    addMessage,
    setAssistantPlaceholder,
    replaceLastAssistantMessage,
  } = useLocalThreads();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // New Chat: Cmd + Shift + O
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === "o") {
        e.preventDefault();
        startNewThread();
      }
      // Toggle Sidebar: Cmd + Shift + S
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === "s") {
        e.preventDefault();
        setSidebarOpen((prev) => !prev);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [startNewThread]);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        threads={threads}
        activeId={activeThreadId}
        onSelect={setActiveById}
        onNew={startNewThread}
        onDelete={deleteThread}
        mode={mode}
        onModeChange={setMode}
      />
      <ChatArea
        activeThread={activeThread}
        addMessage={addMessage}
        setAssistantPlaceholder={setAssistantPlaceholder}
        replaceLastAssistantMessage={replaceLastAssistantMessage}
      />
    </div>
  );
};

export default Index;
