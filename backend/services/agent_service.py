"""Agent CRUD business logic."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.agent import Agent
from backend.models.schemas import AgentCreate, AgentUpdate


class AgentService:
    async def get_by_id(self, db: AsyncSession, agent_id: int) -> Agent | None:
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, payload: AgentCreate) -> Agent:
        agent = Agent(**payload.model_dump())
        db.add(agent)
        await db.flush()
        await db.refresh(agent)
        return agent

    async def update(self, db: AsyncSession, agent_id: int, payload: AgentUpdate) -> Agent | None:
        agent = await self.get_by_id(db, agent_id)
        if not agent:
            return None

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(agent, field, value)

        await db.flush()
        await db.refresh(agent)
        return agent

    async def delete(self, db: AsyncSession, agent_id: int) -> bool:
        agent = await self.get_by_id(db, agent_id)
        if not agent:
            return False
        await db.delete(agent)
        return True
