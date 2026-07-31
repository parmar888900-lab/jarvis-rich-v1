"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, type AppSettings } from "@/lib/api";

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api
      .getSettings()
      .then(setSettings)
      .catch(() =>
        setSettings({
          app_name: "JARVIS AI",
          ollama_base_url: "http://localhost:11434",
          ollama_model: "llama3.2",
          debug: true,
        })
      )
      .finally(() => setLoading(false));
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!settings) return;

    setSaving(true);
    setSaved(false);
    try {
      const updated = await api.updateSettings({
        ollama_base_url: settings.ollama_base_url,
        ollama_model: settings.ollama_model,
        debug: settings.debug,
      });
      setSettings(updated);
      setSaved(true);
    } catch {
      alert("Failed to save settings.");
    } finally {
      setSaving(false);
    }
  }

  if (loading || !settings) {
    return <p className="empty-state">Loading settings...</p>;
  }

  return (
    <>
      <div className="page-header">
        <h1>Settings</h1>
        <p>Configure your local JARVIS AI environment</p>
      </div>

      <form className="card" onSubmit={handleSubmit} style={{ maxWidth: 560 }}>
        <div className="form-group">
          <label>Application Name</label>
          <input type="text" value={settings.app_name} disabled />
        </div>

        <div className="form-group">
          <label>Ollama Base URL</label>
          <input
            type="url"
            value={settings.ollama_base_url}
            onChange={(e) => setSettings({ ...settings, ollama_base_url: e.target.value })}
            placeholder="http://localhost:11434"
          />
        </div>

        <div className="form-group">
          <label>Default Model</label>
          <input
            type="text"
            value={settings.ollama_model}
            onChange={(e) => setSettings({ ...settings, ollama_model: e.target.value })}
            placeholder="llama3.2"
          />
        </div>

        <div className="form-group">
          <label>
            <input
              type="checkbox"
              checked={settings.debug}
              onChange={(e) => setSettings({ ...settings, debug: e.target.checked })}
              style={{ width: "auto", marginRight: "0.5rem" }}
            />
            Debug Mode
          </label>
        </div>

        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? "Saving..." : "Save Settings"}
          </button>
          {saved && <span style={{ color: "var(--success)", fontSize: "0.9rem" }}>Saved!</span>}
        </div>
      </form>

      <div className="card" style={{ maxWidth: 560, marginTop: "1.5rem" }}>
        <h2 style={{ marginBottom: "0.75rem", fontSize: "1.1rem" }}>Local-Only Policy</h2>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
          JARVIS AI uses only open-source, locally-running software. No paid APIs or cloud
          services are required. Models run via Ollama on your machine.
        </p>
      </div>
    </>
  );
}
