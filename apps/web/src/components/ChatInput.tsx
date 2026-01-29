import { useCallback, useRef, useState } from "react";
import { ChevronDown, Paperclip, ArrowUp, Mic } from "lucide-react";
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
    <div className="w-full max-w-3xl mx-auto">
      <div className="bg-secondary/50 border border-white/5 rounded-3xl p-3 shadow-2xl relative group focus:within:border-brand-pink/30 transition-all">
        <AttachmentPreview attachments={attachments} onRemove={onRemoveAttachment} />

        <div className="flex flex-col">
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your message here..."
            rows={1}
            className="w-full px-5 pt-3 pb-2 bg-transparent resize-none focus:outline-none text-white placeholder:text-white/10 text-base font-medium min-h-[44px] max-h-48"
            style={{ fieldSizing: "content" } as React.CSSProperties}
          />

          <div className="flex items-center justify-between px-3 pb-2">
            <div className="flex items-center gap-1">
              <div className="relative">
                <button
                  className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-[10px] font-black uppercase tracking-widest text-white/20 hover:text-white/60 hover:bg-white/5 transition-all"
                  onClick={() => setModelOpen((v) => !v)}
                >
                  {selectedModel}
                  <ChevronDown className={`h-3 w-3 transition-transform ${modelOpen ? 'rotate-180' : ''}`} />
                </button>

                {modelOpen && (
                  <div className="absolute bottom-full mb-3 left-0 w-64 bg-card border border-white/5 rounded-2xl shadow-2xl p-2 z-50 animate-in fade-in zoom-in-95 duration-200">
                    {[
                      "Gemini 2.5 Flash",
                      "Gemini 2.0 Flash",
                    ].map((model) => (
                      <button
                        key={model}
                        className={`w-full text-left px-4 py-2 rounded-xl text-[11px] font-bold uppercase tracking-widest transition-all flex items-center justify-between ${selectedModel === model
                          ? "bg-brand-pink text-white"
                          : "text-white/40 hover:bg-white/5 hover:text-white"
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

              <div className="h-4 w-px bg-white/5 mx-1" />

              <button
                onClick={() => fileInputRef.current?.click()}
                className="p-2 rounded-xl text-white/20 hover:text-white/60 hover:bg-white/5 transition-all"
                title="Attach"
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

              <button className="p-2 rounded-xl text-white/20 hover:text-white/60 hover:bg-white/5 transition-all" title="Mic">
                <Mic className="h-4 w-4" />
              </button>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => onSubmit(attachments)}
                disabled={!value.trim() && attachments.length === 0}
                className={`w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center transition-all disabled:opacity-30 ${value.trim() || attachments.length > 0 ? "bg-brand-pink/20 text-brand-pink shadow-[0_0_20px_rgba(255,46,144,0.2)]" : "text-white/10"
                  }`}
              >
                <ArrowUp className="h-5 w-5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
