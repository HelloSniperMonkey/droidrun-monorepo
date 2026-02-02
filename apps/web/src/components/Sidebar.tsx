import { useMemo, useState } from "react";
import { PanelLeftClose, PanelLeft, Search, Plus, Trash2, Smartphone, Box, Snowflake } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ModeToggle } from "@/components/ui/mode-toggle";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
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
import { ReactNode } from "react";

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
  showSnow: boolean;
  onToggleSnow: () => void;
}

// Helper components for translatable known thread titles
const NewChatTitle = () => <span>New chat</span>;
const ListTabsTitle = () => <span>List tabs</span>;
const OrganizeTabsTitle = () => <span>Organize tabs</span>;
const CloseOldTabsTitle = () => <span>Close old tabs</span>;
const MergeDuplicatesTitle = () => <span>Merge duplicates</span>;
const ListTabSessionsTitle = () => <span>List tab sessions</span>;
const JobPortalsTitle = () => <span>Job portals</span>;
const GoogleSheetsAppsTitle = () => <span>Google Sheets apps</span>;
const GatewayHealthTitle = () => <span>Gateway health</span>;
const CheckAndroidVersionTitle = () => <span>Check Android version</span>;

// Map known English titles to their translatable components
const knownTitles: Record<string, () => JSX.Element> = {
  "New chat": NewChatTitle,
  "List tabs": ListTabsTitle,
  "Organize tabs": OrganizeTabsTitle,
  "Close old tabs": CloseOldTabsTitle,
  "Merge duplicates": MergeDuplicatesTitle,
  "List tab sessions": ListTabSessionsTitle,
  "Job portals": JobPortalsTitle,
  "Google Sheets apps": GoogleSheetsAppsTitle,
  "Gateway health": GatewayHealthTitle,
  "Check Android version": CheckAndroidVersionTitle,
};

// Component to render thread title with translation support
const ThreadTitle = ({ title }: { title: string | undefined }): ReactNode => {
  if (!title) return <NewChatTitle />;

  // Check if this is a known title that should be translated
  const TranslatedComponent = knownTitles[title];
  if (TranslatedComponent) {
    return <TranslatedComponent />;
  }

  // Otherwise show the original title (user's custom text)
  return title;
};

export const Sidebar = ({
  isOpen,
  onToggle,
  threads,
  activeId,
  onSelect,
  onNew,
  onDelete,
  mode,
  onModeChange,
  showPhone,
  onTogglePhone,
  showSnow,
  onToggleSnow
}: SidebarProps) => {
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
    <aside className="w-72 h-screen flex flex-col bg-card border-r border-border relative transition-all duration-300">
      {/* Header */}
      <div className="p-6 flex items-center justify-between">
        <div className="flex items-center gap-3 group cursor-pointer" onClick={onToggle}>
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-pink to-brand-purple flex items-center justify-center rotate-3 group-hover:rotate-12 transition-transform shadow-[0_0_20px_rgba(255,46,144,0.4)]">
            <PanelLeft className="h-4 w-4 text-white" />
          </div>
          <h1 className="text-xl font-black tracking-widest text-white uppercase drop-shadow-md">
            Iron<span className="text-transparent bg-clip-text bg-gradient-to-r from-brand-pink to-brand-purple">Claw</span>
          </h1>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="px-6 pb-6 space-y-3">
        <Button
          onClick={onNew}
          className="w-full h-11 rounded-xl bg-secondary hover:bg-secondary/80 text-white font-bold text-sm border border-white/5 transition-all flex items-center justify-center gap-2"
        >
          <Plus className="h-4 w-4" />
          New Sequence
        </Button>
        <Button
          onClick={onTogglePhone}
          variant="outline"
          className={`w-full h-11 rounded-xl font-bold text-sm transition-all flex items-center justify-center gap-2 ${showPhone
            ? "bg-brand-pink/10 border-brand-pink/30 text-brand-pink"
            : "bg-transparent border-white/10 text-white/60 hover:text-white hover:bg-white/5"
            }`}
        >
          <Smartphone className="h-4 w-4" />
          {showPhone ? <span>Hide UI</span> : <span>Show UI</span>}
        </Button>
      </div>

      {/* Search */}
      <div className="px-6 mb-4">
        <div className="relative group">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/20 group-focus-within:text-brand-pink transition-colors" />
          <input
            type="text"
            placeholder="Search..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-white/[0.03] border border-white/5 focus:border-brand-pink/30 rounded-xl py-2 pl-9 pr-4 text-sm text-white placeholder:text-white/10 outline-none transition-all"
          />
        </div>
      </div>

      {/* Mode Switches */}
      <div className="px-6 mb-6">
        <div className="p-1 bg-white/[0.03] border border-white/5 rounded-xl flex gap-1">
          <button
            onClick={() => onModeChange("local")}
            className={`flex-1 py-1.5 text-[10px] font-black uppercase tracking-widest rounded-lg transition-all ${mode === "local" ? "bg-white text-black" : "text-white/20 hover:text-white/40"
              }`}
          >
            Local
          </button>
          <button
            onClick={() => onModeChange("cloud")}
            className={`flex-1 py-1.5 text-[10px] font-black uppercase tracking-widest rounded-lg transition-all ${mode === "cloud" ? "bg-white text-black" : "text-white/20 hover:text-white/40"
              }`}
          >
            Cloud
          </button>
        </div>
      </div>

      {/* Thread List */}
      <div className="flex-1 overflow-y-auto px-3 custom-scrollbar">
        <div className="px-3 mb-2">
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-white/20">Memory Bank</span>
        </div>
        <div className="space-y-1 pb-8">
          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center opacity-10">
              <Box className="h-8 w-8 mb-3" />
              <p className="text-[10px] font-black uppercase tracking-widest">Sector Empty</p>
            </div>
          ) : (
            filtered.map((thread) => (
              <div
                key={thread.id}
                onClick={() => onSelect(thread.id)}
                className={`group relative flex items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer transition-all ${thread.id === activeId
                  ? "bg-brand-pink/10 text-white"
                  : "text-white/40 hover:text-white/80 hover:bg-white/[0.02]"
                  }`}
              >
                <div className="flex-1 min-w-0 flex items-center gap-3">
                  <div className={`w-1.5 h-1.5 rounded-full transition-all ${thread.id === activeId ? "bg-brand-pink shadow-[0_0_10px_rgba(255,46,144,0.5)]" : "bg-white/10"
                    }`} />
                  <p className="text-sm font-medium truncate">
                    <ThreadTitle title={thread.title} />
                  </p>
                </div>

                <div className="opacity-0 group-hover:opacity-100 transition-opacity ml-2">
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <button
                        onClick={(e) => e.stopPropagation()}
                        className="p-1 px-2 rounded-lg text-white/20 hover:text-destructive hover:bg-destructive/10 transition-all font-bold text-[10px]"
                      >
                        PURGE
                      </button>
                    </AlertDialogTrigger>
                    <AlertDialogContent className="bg-card border-white/5 text-white">
                      <AlertDialogHeader>
                        <AlertDialogTitle className="text-lg font-black uppercase">Purge Memory?</AlertDialogTitle>
                        <AlertDialogDescription className="text-white/40">
                          This core data stream will be permanently erased.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel className="bg-transparent border-white/5 text-white hover:bg-white/5">Cancel</AlertDialogCancel>
                        <AlertDialogAction
                          onClick={(e) => {
                            e.stopPropagation();
                            onDelete(thread.id);
                          }}
                          className="bg-destructive hover:bg-destructive/90 text-white border-none"
                        >
                          Purge
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Snow Toggle - Bottom Section */}
      <div className="p-4 border-t border-white/5 space-y-3">
        {/* Language Switcher */}
        <div className="flex justify-center">
          <LanguageSwitcher />
        </div>

        <button
          onClick={onToggleSnow}
          className={`w-full h-10 rounded-xl font-bold text-xs uppercase tracking-widest transition-all duration-300 flex items-center justify-center gap-2 ${showSnow
            ? "bg-cyan-500/20 border border-cyan-500/40 text-cyan-300 shadow-[0_0_20px_rgba(34,211,238,0.2)]"
            : "bg-white/[0.02] border border-white/10 text-white/50 hover:text-white/80 hover:bg-white/5"
            }`}
        >
          <Snowflake
            className={`h-4 w-4 transition-transform duration-700 ${showSnow ? "animate-spin" : ""}`}
            style={{ animationDuration: "3s" }}
          />
          {showSnow ? <span>Stop Snow</span> : <span>Let it Snow</span>}
        </button>
      </div>

      {/* Footer */}
      <div className="p-6 border-t border-white/5 bg-black/[0.05]">
        <Button
          variant="ghost"
          className="w-full h-12 rounded-xl border border-white/5 bg-white/[0.02] hover:bg-white/5 text-white/40 hover:text-white transition-all flex items-center justify-center gap-3 group"
        >
          <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center group-hover:bg-brand-pink/20 transition-colors">
            <Smartphone className="h-4 w-4 group-hover:text-brand-pink transition-colors" />
          </div>
          <div className="text-left flex-1">
            <p className="text-[10px] mt-1.5 font-black uppercase tracking-widest leading-none">Account Access</p>
            <p className="text-[8px] font-bold text-white/20 uppercase tracking-widest">Log in to sync session</p>
          </div>
        </Button>
      </div>
    </aside>
  );
};

