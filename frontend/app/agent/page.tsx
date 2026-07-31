"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { api, type Agent } from "@/lib/api";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export default function AgentPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.getAgents().then(setAgents).catch(() => setAgents([]));
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleCreateDefault() {
    try {
      const agent = await api.createAgent({
        name: "JARVIS",
        description: "Default local assistant",
        model: "llama3.2",
        system_prompt: "You are JARVIS, a helpful local AI assistant. Be concise and friendly.",
      });
      setAgents((prev) => [agent, ...prev]);
      setSelectedAgent(agent.id);
    } catch {
      alert("Failed to create agent. Is the backend running?");
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!input.trim() || !selectedAgent || loading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setLoading(true);

    try {
      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      const response = await api.chat(selectedAgent, userMessage, history);
      setMessages((prev) => [...prev, { role: "assistant", content: response.message }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error: Could not reach the backend or Ollama." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <div className="page-header">
        <h1>Agent</h1>
        <p>Chat with your local AI agent powered by Ollama</p>
      </div>

      <div style={{ marginBottom: "1rem", display: "flex", gap: "0.75rem", alignItems: "center" }}>
        <select
          value={selectedAgent ?? ""}
          onChange={(e) => {
            setSelectedAgent(Number(e.target.value) || null);
            setMessages([]);
          }}
          style={{
            padding: "0.6rem 1rem",
            background: "var(--bg-secondary)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            color: "var(--text-primary)",
            minWidth: 200,
          }}
        >
          <option value="">Select an agent</option>
          {agents.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name} ({a.model})
            </option>
          ))}
        </select>
        {agents.length === 0 && (
          <button className="btn btn-primary" onClick={handleCreateDefault}>
            Create Default Agent
          </button>
        )}
      </div>

      <div className="card chat-container">
        <div className="chat-messages">
          {messages.length === 0 ? (
            <div className="empty-state">
              {selectedAgent
                ? "Send a message to start chatting."
                : "Select or create an agent to begin."}
            </div>
          ) : (
            messages.map((msg, i) => (
              <div key={i} className={`chat-message ${msg.role}`}>
                {msg.content}
              </div>
            ))
          )}
          {loading && (
            <div className="chat-message assistant">Thinking...</div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form className="chat-input-row" onSubmit={handleSubmit}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            disabled={!selectedAgent || loading}
          />
          <button
            type="submit"
            className="btn btn-primary"
            disabled={!selectedAgent || loading || !input.trim()}
          >
            Send
          </button>
        </form>
      </div>
    </>
  );
}
