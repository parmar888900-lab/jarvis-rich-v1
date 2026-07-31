"use client";

import { useEffect, useState } from "react";
import { api, type AnalyticsSummary } from "@/lib/api";

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    api
      .getAnalytics()
      .then(setAnalytics)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <div className="page-header">
        <h1>Analytics</h1>
        <p>Usage statistics for your local JARVIS AI instance</p>
      </div>

      {loading ? (
        <p className="empty-state">Loading analytics...</p>
      ) : error ? (
        <div className="card">
          <p style={{ color: "var(--danger)" }}>
            Could not load analytics. Make sure the backend is running on port 8000.
          </p>
        </div>
      ) : (
        <>
          <div className="card-grid">
            <div className="stat-card">
              <div className="label">Total Agents</div>
              <div className="value">{analytics?.total_agents ?? 0}</div>
            </div>
            <div className="stat-card">
              <div className="label">Active Agents</div>
              <div className="value">{analytics?.active_agents ?? 0}</div>
            </div>
            <div className="stat-card">
              <div className="label">Total Conversations</div>
              <div className="value">{analytics?.total_conversations ?? 0}</div>
            </div>
            <div className="stat-card">
              <div className="label">Total Messages</div>
              <div className="value">{analytics?.total_messages ?? 0}</div>
            </div>
          </div>

          <div className="card">
            <h2 style={{ marginBottom: "1rem", fontSize: "1.1rem" }}>About Analytics</h2>
            <p style={{ color: "var(--text-secondary)" }}>
              All data is stored locally in SQLite. No usage data is sent to external services.
              Analytics will grow as you create agents and have conversations in Phase 2+.
            </p>
          </div>
        </>
      )}
    </>
  );
}
