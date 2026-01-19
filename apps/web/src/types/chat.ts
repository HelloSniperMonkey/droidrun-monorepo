export type AttachmentKind = "image" | "pdf" | "file";

export interface ChatAttachment {
  id: string;
  name: string;
  kind: AttachmentKind;
  previewUrl?: string;
  uploadedFilename?: string;
  size?: number;
  uploading?: boolean;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
  attachments?: ChatAttachment[];
}

export interface ChatThread {
  id: string;
  title: string;
  messages: ChatMessage[];
  updatedAt: number;
  draftAttachments?: ChatAttachment[];
}
