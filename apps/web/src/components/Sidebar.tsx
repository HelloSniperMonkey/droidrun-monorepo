import { useMemo, useState } from "react";
import { PanelLeftClose, PanelLeft, Search, Plus, LogIn, Pin } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { ChatThread } from "@/types/chat";

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  threads: ChatThread[];
  activeId: string;
  onSelect: (id: string) => void;
  onNew: () => void;
}

export const Sidebar = ({ isOpen, onToggle, threads, activeId, onSelect, onNew }: SidebarProps) => {
  const [searchQuery, setSearchQuery] = useState("");

  const filtered = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) return threads;
    return threads.filter((t) => t.title.toLowerCase().includes(q));
  }, [threads, searchQuery]);

  if (!isOpen) {
    return (
      <Button
        variant="ghost"
        size="icon"
        onClick={onToggle}
        className="fixed left-4 top-4 z-50 text-foreground/70 hover:text-foreground hover:bg-accent"
      >
        <PanelLeft className="h-5 w-5" />
      </Button>
    );
  }

  return (
    <aside className="w-60 h-screen sidebar-gradient flex flex-col border-r border-border/50 slide-in">
      <div className="p-3 flex items-center justify-between">
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggle}
          className="text-foreground/70 hover:text-foreground hover:bg-accent"
        >
          <PanelLeftClose className="h-5 w-5" />
        </Button>
        <h1 className="text-lg font-semibold text-gradient">Iron Claw</h1>
        <div className="w-9" />
      </div>

      <div className="px-3 mb-3">
        <Button onClick={onNew} className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-medium">
          <Plus className="h-4 w-4 mr-2" />
          New Chat
        </Button>
      </div>

      <div className="px-3 mb-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search your threads..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 bg-background/50 border-border/50 focus:border-primary/30 text-sm"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 space-y-1">
        {filtered.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-8">No conversations yet</p>
        ) : (
          filtered.map((thread) => (
            <button
              key={thread.id}
              onClick={() => onSelect(thread.id)}
              className={`w-full text-left px-3 py-2 rounded-lg transition-colors flex items-center gap-2 ${
                thread.id === activeId
                  ? "bg-accent text-accent-foreground border border-border/60"
                  : "hover:bg-accent/70 text-foreground/80"
              }`}
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{thread.title || "New chat"}</p>
                <p className="text-xs text-muted-foreground truncate">
                  {new Date(thread.updatedAt).toLocaleString()}
                </p>
              </div>
              {thread.id === activeId && <Pin className="h-3.5 w-3.5 text-muted-foreground" />}
            </button>
          ))
        )}
      </div>

      <div className="p-3 border-t border-border/50">
        <Button
          variant="ghost"
          className="w-full justify-start text-foreground/70 hover:text-foreground hover:bg-accent"
        >
          <LogIn className="h-4 w-4 mr-2" />
          Login
        </Button>
      </div>
    </aside>
  );
};
