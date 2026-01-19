import { useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { ChatArea } from "@/components/ChatArea";
import { useLocalThreads } from "@/hooks/useLocalThreads";

const Index = () => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const {
    threads,
    activeThread,
    activeThreadId,
    setActiveById,
    startNewThread,
    addMessage,
    setAssistantPlaceholder,
    replaceLastAssistantMessage,
  } = useLocalThreads();

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        threads={threads}
        activeId={activeThreadId}
        onSelect={setActiveById}
        onNew={startNewThread}
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
