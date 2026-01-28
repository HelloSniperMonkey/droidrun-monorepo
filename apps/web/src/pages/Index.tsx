import { useState, useEffect } from "react";
import { Sidebar } from "@/components/Sidebar";
import { ChatArea } from "@/components/ChatArea";
import { DeviceMirror } from "@/components/DeviceMirrorSimple";
import { useLocalThreads } from "@/hooks/useLocalThreads";
import { Smartphone, X } from "lucide-react";
import { Button } from "@/components/ui/button";

const Index = () => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mode, setMode] = useState<"local" | "cloud">("local");
  const [showPhone, setShowPhone] = useState(false);
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
      />

      {/* Main Content Area with Split View */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Chat Area - Takes remaining space */}
        <div
          className={`
            flex-1 min-w-0 transition-all duration-500 ease-[cubic-bezier(0.4,0,0.2,1)]
            ${showPhone ? 'mr-0' : 'mr-0'}
          `}
        >
          <ChatArea
            activeThread={activeThread}
            addMessage={addMessage}
            setAssistantPlaceholder={setAssistantPlaceholder}
            replaceLastAssistantMessage={replaceLastAssistantMessage}
          />
        </div>

        {/* Phone Mirror Panel - Auto width based on content with smooth slide animation */}
        <div
          className={`
            relative overflow-hidden flex-shrink-0
            transition-all duration-500 ease-[cubic-bezier(0.4,0,0.2,1)]
            ${showPhone ? 'w-[400px] opacity-100 translate-x-0' : 'w-0 opacity-0 translate-x-full'}
          `}
          style={{
            background: 'linear-gradient(180deg, hsl(240 10% 6%) 0%, hsl(280 12% 5%) 100%)'
          }}
        >
          {/* Divider with glow effect */}
          <div
            className={`
              absolute left-0 top-0 bottom-0 w-px z-10
              transition-opacity duration-300 delay-100
              ${showPhone ? 'opacity-100' : 'opacity-0'}
            `}
            style={{
              background: 'linear-gradient(180deg, hsl(340 70% 50% / 0.3) 0%, hsl(340 70% 50% / 0.1) 50%, hsl(340 70% 50% / 0.3) 100%)'
            }}
          />
          
          {/* Header with close button */}
          <div
            className={`
              flex items-center justify-between px-4 py-3 border-b border-white/5
              transition-all duration-400 ease-out
              ${showPhone ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-2'}
            `}
            style={{ transitionDelay: showPhone ? '100ms' : '0ms' }}
          >
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-pink-500/10 flex items-center justify-center">
                <Smartphone className="h-4 w-4 text-pink-400" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-200">Device View</h3>
                <p className="text-[10px] text-gray-500">⌘ ⇧ M to toggle</p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-gray-500 hover:text-white hover:bg-white/5"
              onClick={() => setShowPhone(false)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Phone Mirror Container - Full height with padding */}
          <div
            className={`
              p-4 h-[calc(100vh-56px)] flex flex-col
              transition-all duration-400 ease-out
              ${showPhone ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-4'}
            `}
            style={{ transitionDelay: showPhone ? '150ms' : '0ms' }}
          >
            <DeviceMirror />
          </div>
        </div>

        {/* Floating toggle when phone is hidden */}
        {!showPhone && (
          <Button
            onClick={() => setShowPhone(true)}
            className="absolute bottom-6 right-6 h-12 w-12 rounded-full bg-pink-600 hover:bg-pink-500 text-white shadow-lg shadow-pink-500/20 transition-all hover:scale-105"
            size="icon"
            title="Show Phone (⌘ ⇧ M)"
          >
            <Smartphone className="h-5 w-5" />
          </Button>
        )}
      </div>
    </div>
  );
};

export default Index;
