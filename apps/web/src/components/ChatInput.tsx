import { useCallback, useRef, useState } from "react";
import { ChevronDown, ChevronUp, Paperclip, ArrowUp, Mic } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AttachmentPreview } from "./AttachmentPreview";
import type { ChatAttachment } from "@/types/chat";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (attachments: ChatAttachment[]) => void;
  attachments: ChatAttachment[];
  onRemoveAttachment: (id: string) => void;
  onAddFiles: (files: FileList | File[]) => void;
}

export const ChatInput = ({ value, onChange, onSubmit, attachments, onRemoveAttachment, onAddFiles }: ChatInputProps) => {
  const [modelOpen, setModelOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState("Gemini 2.5 Flash");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit(attachments);
    }
  };

  const handleFiles = useCallback(
    (files?: FileList | null) => {
      if (!files || files.length === 0) return;
      onAddFiles(files);
    },
    [onAddFiles],
  );

  return (
    <div className="w-full max-w-3xl mx-auto fade-in" style={{ animationDelay: "0.3s" }}>

      <div
        className="bg-card border border-border rounded-2xl overflow-visible input-glow transition-all"
      >
        <AttachmentPreview attachments={attachments} onRemove={onRemoveAttachment} />

        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type your message here..."
          rows={1}
          className="w-full px-4 pt-4 pb-2 bg-transparent resize-none focus:outline-none text-foreground placeholder:text-muted-foreground min-h-[48px] max-h-32"
          style={{ fieldSizing: "content" } as React.CSSProperties}
        />

        <div className="relative flex items-center justify-between px-3 pb-3">
          <div className="flex items-center gap-2">
            <div className="relative">
              <button
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-primary hover:bg-accent transition-colors"
                onClick={() => setModelOpen((v) => !v)}
              >
                {selectedModel}
                <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
              </button>
              {modelOpen && (
                <div className="absolute bottom-full mb-2 left-0 w-60 bg-card border border-border rounded-xl shadow-lg p-2 space-y-2 z-20">
                  <div className="flex items-center justify-between px-2 text-xs font-medium text-muted-foreground">
                    <span>Choose model</span>
                    <button onClick={() => setModelOpen(false)} className="p-1 text-muted-foreground hover:text-foreground">
                      <ChevronUp className="h-3 w-3" />
                    </button>
                  </div>
                  {[
                    "Gemini 2.5 Flash",
                    "Gemini 2.0 Flash",
                  ].map((model) => (
                    <button
                      key={model}
                      className={`w-full text-left px-3 py-2 rounded-lg text-sm hover:bg-accent transition-colors ${
                        selectedModel === model ? "bg-accent text-accent-foreground" : "text-foreground"
                      }`}
                      onClick={() => {
                        setSelectedModel(model);
                        setModelOpen(false);
                      }}
                    >
                      {model}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <button
              onClick={() => fileInputRef.current?.click()}
              className="p-2 rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
            >
              <Paperclip className="h-4 w-4" />
            </button>

            <input
              type="file"
              multiple
              accept="image/*,application/pdf"
              className="hidden"
              ref={fileInputRef}
              onChange={(e) => handleFiles(e.target.files)}
            />
          </div>

          <div className="flex items-center gap-2">
            <button className="p-2 rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground transition-colors">
              <Mic className="h-4 w-4" />
            </button>
            <Button
              onClick={() => onSubmit(attachments)}
              disabled={!value.trim() && attachments.length === 0}
              size="icon"
              className="h-9 w-9 rounded-full bg-primary hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ArrowUp className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      <p className="text-xs text-muted-foreground text-center mt-2">Press Enter to send, Shift + Enter for new line</p>
    </div>
  );
};
