const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export interface Agent {
  id: number;
  name: string;
  description: string;
  model: string;
  system_prompt: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AnalyticsSummary {
  total_agents: number;
  active_agents: number;
  total_conversations: number;
  total_messages: number;
}

export interface HealthStatus {
  status: string;
  version: string;
  ollama_reachable: boolean;
}

export interface AppSettings {
  app_name: string;
  ollama_base_url: string;
  ollama_model: string;
  debug: boolean;
}

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export const api = {
  getHealth: () => fetchApi<HealthStatus>("/api/health"),
  getAnalytics: () => fetchApi<AnalyticsSummary>("/api/analytics/summary"),
  getAgents: () => fetchApi<Agent[]>("/api/agents/"),
  getSettings: () => fetchApi<AppSettings>("/api/settings/"),
  updateSettings: (data: Partial<AppSettings>) =>
    fetchApi<AppSettings>("/api/settings/", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  chat: (agentId: number, message: string, history: { role: string; content: string }[]) =>
    fetchApi<{ agent_id: number; message: string; model: string }>("/api/agents/chat", {
      method: "POST",
      body: JSON.stringify({ agent_id: agentId, message, history }),
    }),
  createAgent: (data: { name: string; description?: string; model?: string; system_prompt?: string }) =>
    fetchApi<Agent>("/api/agents/", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
