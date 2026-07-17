import type { Analysis, ChatMessage, Document, Health, User } from "./types";

const BASE = import.meta.env.VITE_API_URL ?? "/api";
const TOKEN_KEY = "mindforge:token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const headers = new Headers(options?.headers);
  if (!(options?.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${BASE}${path}`, { ...options, headers });
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
  register: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<User>("/auth/me"),
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
    const token = getToken();
    const headers: HeadersInit = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(`${BASE}/documents/upload`, { method: "POST", body: form, headers });
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
