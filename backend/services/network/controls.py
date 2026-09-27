"""Narrow, owner-only production controls; no action can enable publishing."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.network_channel import NetworkChannel
from backend.models.network_control import NetworkControl


GLOBAL_ACTIONS = {
    "pause_production": ("production_enabled", False),
    "resume_production": ("production_enabled", True),
    "stop_accepting_jobs": ("accept_new_jobs", False),
    "resume_accepting_jobs": ("accept_new_jobs", True),
    "emergency_stop": ("emergency_stop", True),
    "clear_emergency_stop": ("emergency_stop", False),
    "pause_publishing": ("publishing_enabled", False),
}
CHANNEL_ACTIONS = {"pause_channel": True, "resume_channel": False}
CONFIRM_ACTIONS = {"resume_production", "clear_emergency_stop", "resume_channel"}


async def apply_control(db: AsyncSession, action: str, *, channel_id: str | None = None,
                        confirmed: bool = False) -> dict:
    if action in CONFIRM_ACTIONS and not confirmed:
        raise ValueError("Explicit confirmation required")
    if action in GLOBAL_ACTIONS:
        if channel_id:
            raise ValueError("Global action cannot target a channel")
        control = await db.get(NetworkControl, "global")
        if control is None:
            control = NetworkControl(id="global")
            db.add(control)
        field, value = GLOBAL_ACTIONS[action]
        setattr(control, field, value)
        # Public release remains outside the control API under all circumstances.
        await db.commit()
        return {"action": action, "value": value, "publishing_enabled": control.publishing_enabled}
    if action in CHANNEL_ACTIONS:
        channel = await db.get(NetworkChannel, channel_id) if channel_id else None
        if channel is None:
            raise LookupError("Channel not found")
        channel.paused = CHANNEL_ACTIONS[action]
        await db.commit()
        return {"action": action, "channel_id": channel.id, "paused": channel.paused}
    raise ValueError("Unsupported control action")
