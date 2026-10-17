/**
 * API Client for Product API.
 *
 * All requests go to /api/v1/* with JWT Bearer token.
 * Token is stored in localStorage and auto-attached.
 */

const BASE_URL = "/api/v1";

interface RequestConfig {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
}

async function request<T>(path: string, config: RequestConfig = {}): Promise<T> {
  const token = localStorage.getItem("access_token");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(config.headers || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const resp = await fetch(`${BASE_URL}${path}`, {
    method: config.method || "GET",
    headers,
    body: config.body ? JSON.stringify(config.body) : undefined,
  });

  if (resp.status === 204) {
    return null as T;
  }

  const data = await resp.json();

  if (!resp.ok) {
    throw new ApiError(resp.status, data.detail || data.body || "Unknown error", data);
  }

  return data as T;
}

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

// ---------------------------------------------------------------------------
// Auth API
// ---------------------------------------------------------------------------

export interface User {
  id: string;
  email: string;
  display_name: string;
  created_at?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export const authApi = {
  register: (email: string, password: string, displayName: string) =>
    request<User>("/auth/register", {
      method: "POST",
      body: { email, password, display_name: displayName },
    }),

  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: { email, password },
    }),

  me: () => request<User>("/me"),

  logout: (refreshToken?: string) =>
    request<{ status: string }>("/auth/logout", {
      method: "POST",
      body: refreshToken ? { refresh_token: refreshToken } : {},
    }),
};

// ---------------------------------------------------------------------------
// Project API
// ---------------------------------------------------------------------------

export interface Project {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  status: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectList {
  items: Project[];
  total: number;
  offset: number;
  limit: number;
}

export const projectApi = {
  list: (offset = 0, limit = 20) =>
    request<ProjectList>(`/projects?offset=${offset}&limit=${limit}`),

  create: (name: string, description?: string) =>
    request<Project>("/projects", {
      method: "POST",
      body: { name, description },
    }),

  get: (id: string) => request<Project>(`/projects/${id}`),

  update: (id: string, data: { name?: string; description?: string; status?: string }) =>
    request<Project>(`/projects/${id}`, {
      method: "PATCH",
      body: data,
    }),

  delete: (id: string) =>
    request<{ status: string }>(`/projects/${id}`, { method: "DELETE" }),
};

// ---------------------------------------------------------------------------
// Asset API
// ---------------------------------------------------------------------------

export interface Asset {
  id: string;
  project_id: string;
  name: string;
  asset_type: string;
  size_bytes: number;
  s3_url: string | null;
  content_type: string | null;
  created_at: string;
}

export interface AssetList {
  items: Asset[];
  total: number;
  offset: number;
  limit: number;
}

export const assetApi = {
  list: (projectId: string, assetType?: string) =>
    request<AssetList>(`/projects/${projectId}/assets${assetType ? `?asset_type=${assetType}` : ""}`),

  upload: async (projectId: string, file: File) => {
    const token = localStorage.getItem("access_token");
    const formData = new FormData();
    formData.append("file", file);

    const resp = await fetch(`${BASE_URL}/projects/${projectId}/assets`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });

    const data = await resp.json();
    if (!resp.ok) {
      throw new ApiError(resp.status, data.detail || "Upload failed", data);
    }
    return data as Asset;
  },
};

// ---------------------------------------------------------------------------
// Run API
// ---------------------------------------------------------------------------

export interface Run {
  id: string;
  conversation_id: string;
  status: string;
  phase: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export const runApi = {
  create: (data: { conversation_id?: string; user_request: string; profile_id?: string; product_link?: string; input_files?: string[] }) =>
    request<Run>("/runs", { method: "POST", body: data }),

  get: (id: string) => request<Run>(`/runs/${id}`),

  cancel: (id: string) =>
    request<{ run_id: string; status: string }>(`/runs/${id}/cancel`, { method: "POST" }),

  respondToInteraction: (interactionId: string, data: { action: string; content?: unknown }) =>
    request<unknown>(`/interactions/${interactionId}/responses`, {
      method: "POST",
      body: data,
    }),
};

// ---------------------------------------------------------------------------
// SSE Client
// ---------------------------------------------------------------------------

export interface SSEEvent {
  id: string;
  event: string;
  data: Record<string, unknown>;
}

export function createSSEConnection(
  runId: string,
  afterSeq: number,
  onEvent: (event: SSEEvent) => void,
  onError?: (error: Event) => void,
): () => void {
  const token = localStorage.getItem("access_token");
  // EventSource doesn't support custom headers, so pass token as query param
  // For production, use fetch-based SSE instead
  const url = `${BASE_URL}/runs/${runId}/events?after_seq=${afterSeq}&live=true${token ? `&token=${token}` : ""}`;

  const source = new EventSource(url);

  source.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      onEvent({
        id: e.lastEventId || "",
        event: "message",
        data,
      });
    } catch {
      // Heartbeat or comment
    }
  };

  // Listen for named events
  const eventTypes = [
    "run.started", "run.phase_changed", "agent.progress",
    "assistant.delta", "assistant.message",
    "tool.started", "tool.completed", "tool.failed",
    "interaction.requested", "interaction.updated", "interaction.resolved",
    "artifact.created", "business.message",
    "run.completed", "run.failed", "run.cancelled",
  ];

  for (const type of eventTypes) {
    source.addEventListener(type, (e) => {
      const me = e as MessageEvent;
      try {
        const data = JSON.parse(me.data);
        onEvent({ id: me.lastEventId || "", event: type, data });
      } catch {
        // ignore
      }
    });
  }

  source.onerror = (e) => {
    onError?.(e);
  };

  return () => {
    source.close();
  };
}

// ---------------------------------------------------------------------------
// Artifact API
// ---------------------------------------------------------------------------

export interface Artifact {
  id: string;
  run_id: string;
  artifact_type: string;
  uri: string | null;
  status: string;
  created_at: string;
}

export interface ArtifactList {
  items: Artifact[];
  total: number;
}

export const artifactApi = {
  listByProject: (projectId: string) =>
    request<ArtifactList>(`/projects/${projectId}/artifacts`),

  get: (id: string) => request<Artifact>(`/artifacts/${id}`),

  downloadUrl: (id: string) =>
    request<{ download_url: string }>(`/artifacts/${id}/download`),
};

// ---------------------------------------------------------------------------
// Provider API
// ---------------------------------------------------------------------------

export interface ProviderCapability {
  provider_type: string;
  capabilities: string[];
}

export interface ProviderSetting {
  provider_type: string;
  config: Record<string, unknown>;
  is_active: boolean;
}

export const providerApi = {
  list: () => request<ProviderCapability[]>("/providers"),

  listSettings: () => request<ProviderSetting[]>("/provider-settings"),

  setSetting: (providerType: string, config: Record<string, unknown>, isActive = true) =>
    request<ProviderSetting>("/provider-settings", {
      method: "PUT",
      body: { provider_type: providerType, config, is_active: isActive },
    }),
};
