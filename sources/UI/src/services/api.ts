import axios, { AxiosInstance, AxiosResponse } from "axios";
import { TaskStatus } from "@/types";

export interface ArchitectureChatMessage {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

interface ArchitectureChatPayload {
  message: string;
  history?: ArchitectureChatMessage[];
  selection?: Record<string, unknown>;
  architecture?: Record<string, unknown>;
}

interface ArchitectureChatStreamChunk {
  type: "delta" | "done" | "error";
  delta?: string;
  source?: string;
  message?: string;
}

// API configuration
let apiBaseUrl = import.meta.env.VITE_API_URL || "";
if (apiBaseUrl.includes("api:") || apiBaseUrl.includes("://api")) {
  apiBaseUrl = "";
}
const API_BASE_URL = apiBaseUrl;
const API_KEY = import.meta.env.VITE_API_KEY || "test-api-key-12345";

const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${API_KEY}`,
  },
});

const fileUploadApi: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
  headers: {
    Authorization: `Bearer ${API_KEY}`,
  },
});

api.interceptors.request.use(
  (config) => {
    config.headers.Authorization = `Bearer ${API_KEY}`;
    return config;
  },
  (error) => Promise.reject(error),
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      console.error("API authentication failed. Please check your API key.");
    }
    return Promise.reject(error);
  },
);

fileUploadApi.interceptors.request.use(
  (config) => {
    config.headers.Authorization = `Bearer ${API_KEY}`;
    return config;
  },
  (error) => Promise.reject(error),
);

fileUploadApi.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      console.error("API authentication failed. Please check your API key.");
    }
    return Promise.reject(error);
  },
);

// WebSocket service for real-time updates
export class WebSocketService {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private readonly maxReconnectAttempts = 5;
  private readonly reconnectDelay = 1000;
  private readonly listeners = new Map<string, ((data?: unknown) => void)[]>();

  connect(): void {
    try {
      if (
        this.ws &&
        (this.ws.readyState === WebSocket.OPEN ||
          this.ws.readyState === WebSocket.CONNECTING)
      ) {
        return;
      }

      const wsUrl =
        API_BASE_URL === "/api"
          ? "ws://localhost:8000/ws"
          : API_BASE_URL.replace("http", "ws") + "/ws";
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.emit("connected");
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data as string);
          this.emit("message", data);
        } catch {
          console.error("Failed to parse WebSocket message");
        }
      };

      this.ws.onclose = () => {
        this.ws = null;
        this.emit("disconnected");
        this.attemptReconnect();
      };

      this.ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        this.emit("error", error);
      };
    } catch (error) {
      console.error("Failed to create WebSocket connection:", error);
    }
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      setTimeout(() => {
        this.connect();
      }, this.reconnectDelay * this.reconnectAttempts);
    } else {
      console.error("Max reconnection attempts reached");
      this.emit("reconnect_failed");
    }
  }

  on(event: string, callback: (data?: unknown) => void): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event)?.push(callback);
  }

  off(event: string, callback: (data?: unknown) => void): void {
    if (this.listeners.has(event)) {
      const callbacks = this.listeners.get(event)!;
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  private emit(event: string, data?: unknown): void {
    if (this.listeners.has(event)) {
      this.listeners.get(event)?.forEach((cb) => {
        try {
          cb(data);
        } catch (error) {
          console.error("Error in event listener:", error);
        }
      });
    }
  }

  send(data: unknown): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }
}

export const wsService = new WebSocketService();

// Code Architecture API
interface ExtractResponse {
  task_id: string;
  status: string;
  message?: string;
}

export const codeArchitectureAPI = {
  getArchitecture: async (): Promise<unknown> => {
    const response: AxiosResponse = await api.get("/api/v1/code/architecture");
    return response.data;
  },

  extractFromGitHub: async (
    githubUrl: string,
    useGit = true,
    appendMode = true,
    token?: string,
  ): Promise<ExtractResponse> => {
    const body: Record<string, unknown> = {
      github_url: githubUrl,
      use_git: useGit,
      append_mode: appendMode,
    };
    if (token) body.token = token;
    const response: AxiosResponse<ExtractResponse> = await api.post(
      "/api/v1/code/extract-from-github",
      body,
    );
    return response.data;
  },

  extractFromGitHubOrg: async (
    username: string,
    includeForks = false,
    maxRepos = 10,
    appendMode = true,
  ): Promise<ExtractResponse> => {
    const response: AxiosResponse<ExtractResponse> = await api.post(
      "/api/v1/code/extract-from-github-org",
      {
        github_username: username,
        include_forks: includeForks,
        max_repos: maxRepos,
        append_mode: appendMode,
      },
      { timeout: 60000 },
    );
    return response.data;
  },

  scanLocalPath: async (
    repoPath: string,
    appendMode = true,
  ): Promise<ExtractResponse> => {
    const response: AxiosResponse<ExtractResponse> = await api.post(
      "/api/v1/code/scan",
      { repo_path: repoPath, use_c4_model: true, append_mode: appendMode },
    );
    return response.data;
  },

  clearArchitecture: async (): Promise<{
    status: string;
    message: string;
    deleted_count: number;
  }> => {
    const response = await api.post("/api/v1/code/clear");
    return response.data;
  },

  getExtractionStatus: async (taskId: string): Promise<TaskStatus> => {
    const response: AxiosResponse<TaskStatus> = await api.get(
      `/api/v1/code/scan/${taskId}`,
    );
    return response.data;
  },

  getExtractionResults: async (taskId: string): Promise<unknown> => {
    const response: AxiosResponse = await api.get(
      `/api/v1/code/scan/${taskId}/results`,
    );
    return response.data;
  },

  describeNode: async (payload: {
    id?: string;
    name?: string;
    type?: string;
    level?: string;
    attributes?: Record<string, unknown>;
    containerMeta?: Record<string, unknown>;
    file?: string;
  }): Promise<{ description: string; source: string }> => {
    const response: AxiosResponse = await api.post(
      "/api/v1/code/describe/node",
      payload,
    );
    return response.data;
  },

  describeEdge: async (payload: {
    id?: string;
    source?: string;
    target?: string;
    label?: string;
    relationshipType?: string;
    protocol?: string;
  }): Promise<{ description: string; source: string }> => {
    const response: AxiosResponse = await api.post(
      "/api/v1/code/describe/edge",
      payload,
    );
    return response.data;
  },

  chatWithContext: async (
    payload: ArchitectureChatPayload,
  ): Promise<{ message: string; source: string }> => {
    const response: AxiosResponse = await api.post(
      "/api/v1/code/chat/context",
      payload,
    );
    return response.data;
  },

  streamChatWithContext: async (
    payload: ArchitectureChatPayload,
    handlers: {
      onDelta: (delta: string) => void;
      onComplete?: (source: string) => void;
      signal?: AbortSignal;
    },
  ): Promise<void> => {
    const controller = new AbortController();
    const signal = handlers.signal ?? controller.signal;

    if (handlers.signal) {
      handlers.signal.addEventListener("abort", () => {
        controller.abort();
      });
    }

    const response = await fetch(`${API_BASE_URL}/api/v1/code/chat/context`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${API_KEY}`,
      },
      body: JSON.stringify({ ...payload, stream: true }),
      signal,
    });

    if (!response.ok || !response.body) {
      throw new Error(
        `Architecture chat failed with status ${response.status}`,
      );
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let source = "heuristic";
    let completed = false;

    try {
      while (true) {
        if (signal.aborted) {
          reader.cancel();
          break;
        }

        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        let newlineIndex = buffer.indexOf("\n");

        while (newlineIndex >= 0) {
          const line = buffer.slice(0, newlineIndex).trim();
          buffer = buffer.slice(newlineIndex + 1);

          if (line) {
            const chunk = JSON.parse(line) as ArchitectureChatStreamChunk;
            if (chunk.source) source = chunk.source;
            if (chunk.type === "delta" && chunk.delta) {
              handlers.onDelta(chunk.delta);
            } else if (chunk.type === "done") {
              completed = true;
              handlers.onComplete?.(source);
            } else if (chunk.type === "error") {
              throw new Error(
                chunk.message || "Architecture chat stream failed",
              );
            }
          }

          newlineIndex = buffer.indexOf("\n");
        }
      }

      if (buffer.trim()) {
        const chunk = JSON.parse(buffer.trim()) as ArchitectureChatStreamChunk;
        if (chunk.source) source = chunk.source;
        if (chunk.type === "delta" && chunk.delta) {
          handlers.onDelta(chunk.delta);
        } else if (chunk.type === "done") {
          completed = true;
          handlers.onComplete?.(source);
        }
      }

      if (!completed) handlers.onComplete?.(source);
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      throw err;
    }
  },
};

export type LLMConfigResponse = {
  model: string;
  api_key_set: boolean;
  api_key_source: string;
  rate_limit_used: number;
  rate_limit_max: number;
};

export const llmConfigAPI = {
  getConfig: async (): Promise<LLMConfigResponse> => {
    const response: AxiosResponse<LLMConfigResponse> = await api.get("/api/v1/config/llm/");
    return response.data;
  },
  updateConfig: async (patch: Partial<{ api_key: string; model: string }>): Promise<LLMConfigResponse> => {
    const response: AxiosResponse<LLMConfigResponse> = await api.put("/api/v1/config/llm/", patch);
    return response.data;
  },
};

export default api;
