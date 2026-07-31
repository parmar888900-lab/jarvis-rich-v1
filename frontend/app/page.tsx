"use client";

import { useEffect, useState } from "react";
import { api, type AnalyticsSummary, type HealthStatus } from "@/lib/api";

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [healthData, analyticsData] = await Promise.all([
          api.getHealth(),
          api.getAnalytics(),
        ]);
        setHealth(healthData);
        setAnalytics(analyticsData);
      } catch {
        setHealth({ status: "offline", version: "0.1.0", ollama_reachable: false });
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <>
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>Overview of your local JARVIS AI system</p>
      </div>

      {loading ? (
        <p className="empty-state">Loading...</p>
      ) : (
        <>
          <div className="card-grid">
            <div className="stat-card">
              <div className="label">System Status</div>
              <div className="value" style={{ fontSize: "1.1rem" }}>
                <span
                  className={`status-badge ${health?.ollama_reachable ? "online" : "offline"}`}
                >
                  {health?.ollama_reachable ? "Ollama Online" : "Ollama Offline"}
                </span>
              </div>
            </div>
            <div className="stat-card">
              <div className="label">Total Agents</div>
              <div className="value">{analytics?.total_agents ?? 0}</div>
            </div>
            <div className="stat-card">
              <div className="label">Active Agents</div>
              <div className="value">{analytics?.active_agents ?? 0}</div>
            </div>
            <div className="stat-card">
              <div className="label">Conversations</div>
              <div className="value">{analytics?.total_conversations ?? 0}</div>
            </div>
          </div>

          <div className="card">
            <h2 style={{ marginBottom: "1rem", fontSize: "1.1rem" }}>Quick Start</h2>
            <ol style={{ paddingLeft: "1.25rem", color: "var(--text-secondary)", lineHeight: 2 }}>
              <li>Install <a href="https://ollama.com" target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>Ollama</a> locally</li>
              <li>Pull a model: <code style={{ background: "var(--bg-secondary)", padding: "0.2rem 0.5rem", borderRadius: 4 }}>ollama pull llama3.2</code></li>
              <li>Start the backend: <code style={{ background: "var(--bg-secondary)", padding: "0.2rem 0.5rem", borderRadius: 4 }}>uvicorn app:app --reload</code></li>
              <li>Go to the <a href="/agent" style={{ color: "var(--accent)" }}>Agent page</a> to chat</li>
            </ol>
          </div>
        </>
      )}
    </>
  );
}
