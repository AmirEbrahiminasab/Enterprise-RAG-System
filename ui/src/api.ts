import type { Chat, KnowledgeDocument, Message } from "./types";

const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(
    /\/$/,
    "",
  ) ?? "/api";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

async function errorFrom(response: Response): Promise<ApiError> {
  let message = `Request failed (${response.status})`;
  try {
    const body = (await response.json()) as {
      detail?: string;
      message?: string;
    };
    message = body.detail ?? body.message ?? message;
  } catch {
    // The API may return an empty or non-JSON error response.
  }
  return new ApiError(message, response.status);
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) throw await errorFrom(response);
  return response.json() as Promise<T>;
}

export const api = {
  async login(email: string, password: string) {
    const body = new URLSearchParams({ username: email, password });
    return request<{ access_token: string; token_type: string }>("/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
  },

  signup(name: string, email: string, password: string) {
    return request<{ message: string; user_id: string }>("/signup", {
      method: "POST",
      body: JSON.stringify({ name, email, password }),
    });
  },

  async chats(token: string): Promise<Chat[]> {
    try {
      const data = await request<{ chats: Chat[] }>("/chat", {}, token);
      return data.chats;
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return [];
      throw error;
    }
  },

  createChat(token: string, title: string) {
    return request<{ message: string }>(
      "/new_chat",
      {
        method: "POST",
        body: JSON.stringify({ title }),
      },
      token,
    );
  },

  async messages(token: string, chatId: string): Promise<Message[]> {
    try {
      const data = await request<{ messages: Message[] }>(
        `/chat/${chatId}/messages`,
        {},
        token,
      );
      return data.messages;
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return [];
      throw error;
    }
  },

  async documents(token: string, chatId: string): Promise<KnowledgeDocument[]> {
    try {
      const data = await request<{ documents: KnowledgeDocument[] }>(
        `/chat/${chatId}/documents`,
        {},
        token,
      );
      return data.documents;
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return [];
      throw error;
    }
  },

  async upload(token: string, chatId: string, file: File) {
    const formData = new FormData();
    formData.append("file", file);
    return request<{ message: string }>(
      `/chat/${chatId}/upload`,
      {
        method: "POST",
        body: formData,
      },
      token,
    );
  },

  async streamMessage(
    token: string,
    chatId: string,
    content: string,
    onChunk: (text: string) => void,
    signal?: AbortSignal,
  ): Promise<string> {
    const response = await fetch(`${API_BASE}/chat/${chatId}/new_message`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ content }),
      signal,
    });

    if (!response.ok) throw await errorFrom(response);
    if (!response.body)
      throw new ApiError("Streaming is not supported by this browser", 0);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let answer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      answer += chunk;
      onChunk(chunk);
    }

    const finalChunk = decoder.decode();
    if (finalChunk) {
      answer += finalChunk;
      onChunk(finalChunk);
    }
    return answer;
  },
};
