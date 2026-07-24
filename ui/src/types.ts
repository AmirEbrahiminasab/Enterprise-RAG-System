export type DocumentStatus = "pending" | "processing" | "completed" | "failed";

export interface Chat {
  id: string;
  title: string;
  created_at: string;
  user_id: string;
}

export interface Message {
  id?: string;
  content: string;
  sent_at?: string;
  chat_id?: string;
  role: "user" | "system" | "assistant";
  pending?: boolean;
  failed?: boolean;
}

export interface KnowledgeDocument {
  id: string;
  title: string;
  uploaded_at: string;
  chat_id: string;
  status: DocumentStatus;
}

export interface Session {
  token: string;
  email: string;
  name?: string;
}
