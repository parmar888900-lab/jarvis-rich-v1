"""Analytics endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.agent import Agent, Conversation, Message
from models.schemas import AnalyticsSummary

router = APIRouter()


@router.get("/summary", response_model=AnalyticsSummary)
async def get_summary(db: AsyncSession = Depends(get_db)):
    total_agents = await db.scalar(select(func.count()).select_from(Agent)) or 0
    active_agents = await db.scalar(
        select(func.count()).select_from(Agent).where(Agent.is_active.is_(True))
    ) or 0
    total_conversations = await db.scalar(select(func.count()).select_from(Conversation)) or 0
    total_messages = await db.scalar(select(func.count()).select_from(Message)) or 0

    return AnalyticsSummary(
        total_agents=total_agents,
        active_agents=active_agents,
        total_conversations=total_conversations,
        total_messages=total_messages,
    )
