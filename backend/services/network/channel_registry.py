"""Validated channel registration without guessing any YouTube account state."""

from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.network_channel import CHANNEL_STATES, NetworkChannel


class ChannelRegistry:
    async def register(self, session: AsyncSession, *, name: str, niche: str,
                       editorial_identity: str, timezone: str = "UTC",
                       handle: str | None = None, max_daily_posts: int = 4,
                       topic_universe: list[str] | None = None,
                       allowed_topics: list[str] | None = None,
                       blocked_topics: list[str] | None = None,
                       posting_windows: list[dict] | None = None,
                       profiles: dict[str, dict] | None = None) -> NetworkChannel:
        name, niche, editorial_identity = (
            name.strip(), niche.strip(), editorial_identity.strip()
        )
        if not all((name, niche, editorial_identity)):
            raise ValueError("Channel name, niche and unique editorial identity are required")
        if isinstance(max_daily_posts, bool) or not 0 <= max_daily_posts <= 4:
            raise ValueError("Daily posting maximum must be 0 through 4")
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
            raise ValueError("Use a real IANA timezone") from exc
        profiles = profiles or {}
        if set(profiles) - {"branding", "voice", "visual", "caption", "metadata"}:
            raise ValueError("Unknown channel profile")
        if any(not isinstance(item, dict) for item in profiles.values()):
            raise ValueError("Channel profiles must be objects")
        allowed = [str(item).strip() for item in allowed_topics or []]
        blocked = [str(item).strip() for item in blocked_topics or []]
        if set(map(str.casefold, allowed)) & set(map(str.casefold, blocked)):
            raise ValueError("A topic cannot be both allowed and blocked")
        channel = NetworkChannel(
            name=name, niche=niche, editorial_identity=editorial_identity,
            handle=handle.strip() if handle else None,
            timezone=timezone, max_daily_posts=max_daily_posts,
            topic_universe=topic_universe or [], allowed_topics=allowed,
            blocked_topics=blocked, posting_windows=posting_windows or [],
            branding_profile=profiles.get("branding", {}),
            voice_profile=profiles.get("voice", {}),
            visual_profile=profiles.get("visual", {}),
            caption_profile=profiles.get("caption", {}),
            metadata_profile=profiles.get("metadata", {}),
            lifecycle_state="PLANNED",
        )
        session.add(channel)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise ValueError("Channel identity or handle is already registered") from exc
        await session.refresh(channel)
        return channel

    async def list_channels(self, session: AsyncSession) -> list[NetworkChannel]:
        result = await session.execute(select(NetworkChannel).order_by(NetworkChannel.created_at,
                                                                        NetworkChannel.id))
        return list(result.scalars().all())

    async def set_state(self, session: AsyncSession, channel_id: str,
                        state: str, *, reason: str | None = None) -> NetworkChannel:
        if state not in CHANNEL_STATES:
            raise ValueError("Invalid channel lifecycle state")
        channel = await session.get(NetworkChannel, channel_id)
        if channel is None:
            raise LookupError("Channel not found")
        channel.lifecycle_state = state
        channel.paused = state == "PAUSED" or channel.paused and state != "ACTIVE"
        channel.degraded_reason = reason.strip() if reason else None
        await session.commit()
        await session.refresh(channel)
        return channel
