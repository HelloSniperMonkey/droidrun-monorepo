import { X } from "lucide-react";
import type { ChatAttachment } from "@/types/chat";

interface AttachmentPreviewProps {
  attachments: ChatAttachment[];
  onRemove: (id: string) => void;
}

export const AttachmentPreview = ({ attachments, onRemove }: AttachmentPreviewProps) => {
  if (!attachments.length) return null;

  return (
    <div className="flex gap-3 items-start px-2 pt-3 pb-3 overflow-x-auto">
      {attachments.map((file) => {
        const isImage = file.kind === "image" && file.previewUrl;
        const extension = (file.name?.split(".").pop() || file.kind || "FILE").toUpperCase();
        const isPdf = extension === "PDF" || file.kind === "pdf";
        return (
          <div
            key={file.id}
            className={`relative shrink-0 ${isImage ? "" : "min-w-[260px]"} ${file.uploading ? "opacity-50" : ""}`}
          >
            <div
              className={`flex items-center gap-3 rounded-2xl border border-border/70 bg-card/90 shadow-sm px-3 py-2 ${
                isImage ? "pr-5" : "pr-10"
              }`}
            >
              {isImage ? (
                <img
                  src={file.previewUrl}
                  alt={file.name}
                  className="h-16 w-16 rounded-xl object-cover"
                />
              ) : (
                <div className={`h-14 w-14 rounded-xl flex items-center justify-center text-xs font-semibold ${isPdf ? "bg-red-500/90 text-white" : "bg-white/10 text-white/70"}`}>
                  {extension}
                </div>
              )}
              <div className="max-w-[200px]">
                <p className="text-sm font-semibold text-foreground truncate">{file.name}</p>
                <p className="text-xs text-muted-foreground uppercase">{extension}</p>
              </div>
            </div>
            <button
              onClick={() => onRemove(file.id)}
              className="absolute top-0 right-0 h-6 w-6 rounded-full bg-background border border-border shadow flex items-center justify-center text-foreground hover:bg-muted"
              aria-label="Remove attachment"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        );
      })}
    </div>
  );
};
