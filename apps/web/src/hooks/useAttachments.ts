import { useState, useCallback } from "react";
import type { ChatAttachment } from "@/types/chat";
import { api } from "@/lib/api";

const MAX_PREVIEW_SIZE = 15 * 1024 * 1024; // 15MB preview cap

export function useAttachments() {
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [uploadingIds, setUploadingIds] = useState<string[]>([]);

  const addFiles = useCallback(async (files: FileList | File[]) => {
    const list = Array.from(files);
    for (const file of list) {
      const id = crypto.randomUUID();
      const kind = file.type.startsWith("image") ? "image" : file.type === "application/pdf" ? "pdf" : "file";
      const previewUrl = kind === "image" && file.size < MAX_PREVIEW_SIZE ? URL.createObjectURL(file) : undefined;
      
      const optimisticAttachment: ChatAttachment = {
        id,
        name: file.name,
        kind,
        previewUrl,
        size: file.size,
        uploading: true,
      };

      setAttachments((prev) => [...prev, optimisticAttachment]);
      setUploadingIds((prev) => [...prev, id]);

      try {
        const res = await api.upload(file);
        setAttachments((prev) =>
          prev.map((a) => (a.id === id ? { ...a, uploadedFilename: res.filename, uploading: false } : a))
        );
      } catch (err) {
        console.error("Upload failed", err);
        setAttachments((prev) =>
          prev.map((a) => (a.id === id ? { ...a, uploading: false } : a))
        );
      } finally {
        setUploadingIds((prev) => prev.filter((x) => x !== id));
      }
    }
  }, []);

  const removeAttachment = useCallback((id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  }, []);

  const reset = useCallback(() => setAttachments([]), []);

  return {
    attachments,
    uploadingIds,
    addFiles,
    removeAttachment,
    reset,
  };
}
