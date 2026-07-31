"""Agent management and chat endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.agent import Agent
from models.schemas import AgentCreate, AgentResponse, AgentUpdate, ChatRequest, ChatResponse
from services.agent_service import AgentService
from services.llm_service import LLMService

router = APIRouter()
agent_service = AgentService()
llm_service = LLMService()


@router.get("/", response_model=list[AgentResponse])
async def list_agents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).order_by(Agent.created_at.desc()))
    return result.scalars().all()


@router.post("/", response_model=AgentResponse, status_code=201)
async def create_agent(payload: AgentCreate, db: AsyncSession = Depends(get_db)):
    return await agent_service.create(db, payload)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    agent = await agent_service.get_by_id(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: int, payload: AgentUpdate, db: AsyncSession = Depends(get_db)):
    agent = await agent_service.update(db, agent_id, payload)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    deleted = await agent_service.delete(db, agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    agent = await agent_service.get_by_id(db, payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    messages = [{"role": "system", "content": agent.system_prompt}]
    messages.extend({"role": m.role, "content": m.content} for m in payload.history)
    messages.append({"role": "user", "content": payload.message})

    reply = await llm_service.chat(messages, model=agent.model)
    return ChatResponse(agent_id=agent.id, message=reply, model=agent.model)
