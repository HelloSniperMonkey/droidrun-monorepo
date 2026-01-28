import { useMemo, useState } from "react";
import { PanelLeftClose, PanelLeft, Search, Plus, LogIn, Trash2, Smartphone } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ModeToggle } from "@/components/ui/mode-toggle";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import type { ChatThread } from "@/types/chat";

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  threads: ChatThread[];
  activeId: string;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  mode: "local" | "cloud";
  onModeChange: (mode: "local" | "cloud") => void;
  showPhone: boolean;
  onTogglePhone: () => void;
}

export const Sidebar = ({ isOpen, onToggle, threads, activeId, onSelect, onNew, onDelete, mode, onModeChange, showPhone, onTogglePhone }: SidebarProps) => {
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
        <ModeToggle mode={mode} onChange={onModeChange} />
      </div>

      <div className="px-3 mb-3">
        <Button
          variant={showPhone ? "default" : "ghost"}
          className={`w-full justify-start gap-2 transition-all ${
            showPhone 
              ? "bg-pink-600/20 text-pink-400 hover:bg-pink-600/30 border border-pink-500/30" 
              : "hover:bg-accent text-foreground/70 hover:text-foreground"
          }`}
          onClick={onTogglePhone}
        >
          <Smartphone className="h-4 w-4" />
          <span className="flex-1 text-left">{showPhone ? "Hide Phone" : "Show Phone"}</span>
          <span className="text-[10px] opacity-50 font-normal">⌘⇧M</span>
        </Button>
      </div>

      <div className="px-3 mb-3">
        <Button onClick={onNew} className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-medium justify-between">
          <div className="flex items-center">
            <Plus className="h-4 w-4 mr-2" />
            New Chat
          </div>
          <div className="flex items-center gap-1 text-xs opacity-60 font-normal">
            <span className="text-[10px]">⇧</span>
            <span className="text-[10px]">⌘</span>
            <span>O</span>
          </div>
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
            <div
              key={thread.id}
              onClick={() => onSelect(thread.id)}
              className={`w-full text-left px-3 py-2 rounded-lg transition-colors flex items-center gap-2 cursor-pointer group ${thread.id === activeId
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
              {thread.id === activeId && (
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <button
                      onClick={(e) => e.stopPropagation()}
                      className="text-muted-foreground hover:text-destructive transition-colors p-1"
                      title="Delete chat"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </AlertDialogTrigger>
                  <AlertDialogContent onClick={(e) => e.stopPropagation()}>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Delete chat?</AlertDialogTitle>
                      <AlertDialogDescription>
                        This will permanently delete this conversation. This action cannot be undone.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel onClick={(e) => e.stopPropagation()}>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={(e) => {
                          e.stopPropagation();
                          onDelete(thread.id);
                        }}
                        autoFocus
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      >
                        Delete
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              )}
            </div>
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
