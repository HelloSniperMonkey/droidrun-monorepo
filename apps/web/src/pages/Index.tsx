import { useState, useEffect } from "react";
import { Sidebar } from "@/components/Sidebar";
import { ChatArea } from "@/components/ChatArea";
import { DeviceMirrorWebRTC as DeviceMirror } from "@/components/DeviceMirrorWebRTC";
import { SnowAnimation } from "@/components/SnowAnimation";
import { useLocalThreads } from "@/hooks/useLocalThreads";
import { Smartphone } from "lucide-react";
import { Button } from "@/components/ui/button";

const Index = () => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mode, setMode] = useState<"local" | "cloud">("local");
  const [showPhone, setShowPhone] = useState(false);
  const [showSnow, setShowSnow] = useState(false);
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
      // Toggle Phone: Cmd + Shift + M
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === "m") {
        e.preventDefault();
        setShowPhone((prev) => !prev);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [startNewThread]);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <SnowAnimation isActive={showSnow} />
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
        showPhone={showPhone}
        onTogglePhone={() => setShowPhone(!showPhone)}
        showSnow={showSnow}
        onToggleSnow={() => setShowSnow(!showSnow)}
      />

      <main className="flex-1 flex overflow-hidden relative">
        <div className="flex-1 min-w-0 bg-background relative z-0">
          <ChatArea
            activeThread={activeThread}
            addMessage={addMessage}
            setAssistantPlaceholder={setAssistantPlaceholder}
            replaceLastAssistantMessage={replaceLastAssistantMessage}
          />
        </div>

        {/* Phone Mirror Panel */}
        <div
          className={`
            relative overflow-hidden flex-shrink-0 bg-card border-l border-white/5
            transition-all duration-700
            ${showPhone ? 'w-[500px] opacity-100' : 'w-0 opacity-0'}
          `}
          style={{ transitionTimingFunction: 'cubic-bezier(0.23,1,0.32,1)' }}
        >
          <div className="relative h-full flex flex-col z-10">
            <DeviceMirror />

            <button
              onClick={() => setShowPhone(false)}
              className="absolute top-1/2 -left-3 w-6 h-12 bg-white/5 border border-white/10 rounded-full flex items-center justify-center text-white/20 hover:text-white transition-all z-50 group hover:bg-white/10"
            >
              <div className="w-1 h-4 bg-current rounded-full transition-transform group-hover:scale-y-125" />
            </button>
          </div>
        </div>

        {/* Floating toggle when phone is hidden */}
        {!showPhone && (
          <div className="absolute bottom-10 right-10 animate-in fade-in slide-in-from-bottom-4 duration-1000">
            <button
              onClick={() => setShowPhone(true)}
              className="h-14 w-14 rounded-2xl bg-brand-pink text-white shadow-[0_0_30px_rgba(255,46,144,0.3)] transition-all hover:scale-110 active:scale-95 flex items-center justify-center group border-none relative"
            >
              <Smartphone className="h-6 w-6 transition-transform group-hover:rotate-12" />
              <div className="absolute -top-1 -right-1 w-3 h-3 bg-white rounded-full border-2 border-brand-pink animate-pulse" />
            </button>
          </div>
        )}
      </main>
    </div>
  );
};

export default Index;
