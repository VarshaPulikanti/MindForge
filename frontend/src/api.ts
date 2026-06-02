import type { Analysis, ChatMessage, Document, Health } from "./types";

const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = err.detail;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  health: () => request<Health>("/health"),
  listDocuments: () => request<Document[]>("/documents"),
  createDocument: (title: string, content: string) =>
    request<Document>("/documents", {
      method: "POST",
      body: JSON.stringify({ title, content }),
    }),
  uploadDocument: async (file: File, title?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (title) form.append("title", title);
    const res = await fetch(`${BASE}/documents/upload`, { method: "POST", body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? "Upload failed");
    }
    return res.json() as Promise<Document>;
  },
  deleteDocument: (id: number) =>
    request<void>(`/documents/${id}`, { method: "DELETE" }),
  analyze: (id: number) =>
    request<Analysis>(`/documents/${id}/analyze`, { method: "POST" }),
  listAnalyses: (id: number) => request<Analysis[]>(`/documents/${id}/analyses`),
  listMessages: (id: number) => request<ChatMessage[]>(`/documents/${id}/messages`),
  clearMessages: (id: number) =>
    request<void>(`/documents/${id}/messages`, { method: "DELETE" }),
  chat: (id: number, message: string) =>
    request<ChatMessage[]>(`/documents/${id}/chat`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
};
