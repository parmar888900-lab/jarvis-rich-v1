"""Pydantic schemas for API request/response validation."""

from datetime import datetime

from pydantic import BaseModel, Field


class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    model: str = Field(default="qwen2.5:7b")
    system_prompt: str = Field(default="You are JARVIS, a helpful local AI assistant.")


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    model: str | None = None
    system_prompt: str | None = None
    is_active: bool | None = None


class AgentResponse(AgentBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class ChatRequest(BaseModel):
    agent_id: int
    message: str = Field(..., min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    agent_id: int
    message: str
    model: str


class AnalyticsSummary(BaseModel):
    total_agents: int
    total_conversations: int
    total_messages: int
    active_agents: int


class SettingsResponse(BaseModel):
    app_name: str
    ollama_base_url: str
    ollama_model: str
    debug: bool


class SettingsUpdate(BaseModel):
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    debug: bool | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    ollama_reachable: bool
