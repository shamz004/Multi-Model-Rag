export type Doc = {
  id: string;
  filename: string;
  size_bytes: number;
  pages: number;
  chunks: number;
  status: "processing" | "ready" | "failed" | "rejected";
  error: string | null;
  created_at: string;
  duplicate?: boolean;
};

export type Source = {
  n: number;
  chunk_id: number;
  document_id: string;
  filename: string;
  page: number;
  text: string;
  similarity: number | null;
  cited: boolean;
};

export type Message = {
  id: number | string;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  answerable: boolean | null;
  rewritten?: string;
  error?: boolean;
};

export type Conversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type Health = {
  status: string;
  openai_configured: boolean;
  chat_model: string;
  embedding_model: string;
  indexed_chunks: number;
};

export type ChatEvent =
  | { type: "conversation"; conversation: Conversation }
  | { type: "rewrite"; question: string }
  | { type: "sources"; sources: Source[] }
  | { type: "token"; text: string }
  | { type: "done"; message: Message }
  | { type: "error"; message: string };

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* keep the generic message */
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => request<Health>("/api/health"),
  documents: () => request<Doc[]>("/api/documents"),
  upload: (files: File[]) => {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    return request<Doc[]>("/api/documents", { method: "POST", body: form });
  },
  deleteDocument: (id: string) => request(`/api/documents/${id}`, { method: "DELETE" }),
  conversations: () => request<Conversation[]>("/api/conversations"),
  conversation: (id: string) =>
    request<Conversation & { messages: Message[] }>(`/api/conversations/${id}`),
  renameConversation: (id: string, title: string) =>
    request<Conversation>(`/api/conversations/${id}`, { method: "PATCH", ...json({ title }) }),
  deleteConversation: (id: string) => request(`/api/conversations/${id}`, { method: "DELETE" }),
};

export const pdfUrl = (source: Pick<Source, "document_id" | "page">) =>
  `/api/documents/${source.document_id}/file#page=${source.page}`;

/** Sends a question and calls `onEvent` for every server-sent event of the answer. */
export async function streamChat(
  body: { question: string; conversation_id: string | null; document_ids: string[] | null },
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch("/api/chat", { method: "POST", signal, ...json(body) });
  if (!response.ok || !response.body) {
    let detail = `Request failed (${response.status})`;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") detail = data.detail;
    } catch {
      /* keep the generic message */
    }
    throw new Error(detail);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      if (frame.startsWith("data: ")) onEvent(JSON.parse(frame.slice(6)) as ChatEvent);
    }
  }
}
