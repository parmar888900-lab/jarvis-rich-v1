"""Narrow network commands shared by microphone, dashboard voice and text."""

import re
from pathlib import Path

from sqlalchemy import select

from backend.models.network_channel import NetworkChannel
from backend.services.network.controls import apply_control
from backend.services.network.status import network_snapshot


def parse_network_command(text: str) -> tuple[str, str | None, bool] | None:
    normalized = " ".join(text.casefold().strip(" .,!?\t\r\n").split())
    if re.fullmatch(r"how many videos? (?:are|is) rendering(?: right now)?", normalized):
        return "rendering_count", None, False
    if re.fullmatch(r"what failed (?:overnight|today)", normalized):
        return "recent_failures", None, False
    if normalized == "stop publishing but keep rendering":
        return "pause_publishing", None, False
    if normalized == "pause production":
        return "pause_production", None, False
    if normalized in {"resume production", "confirm resume production"}:
        return "resume_production", None, normalized.startswith("confirm ")
    match = re.fullmatch(r"(pause|resume|confirm resume) (?:channel )?([\w -]{2,80})", normalized)
    if match:
        verb, name = match.groups()
        return ("pause_channel" if verb == "pause" else "resume_channel",
                name, verb.startswith("confirm "))
    return None


async def route_network_command(text: str, sessions, *, root: Path) -> dict | None:
    parsed = parse_network_command(text)
    if parsed is None:
        return None
    action, name, confirmed = parsed
    if action in {"resume_production", "resume_channel"} and not confirmed:
        return {"status": "confirmation_required", "task": action,
                "message": f"Say confirm {text.strip()} to resume."}
    async with sessions() as db:
        if action == "rendering_count":
            snap = await network_snapshot(db, storage_path=root)
            count = snap["job_counts"].get("RENDERING", 0)
            return {"status": "completed", "task": action,
                    "message": f"{count} video{'s' if count != 1 else ''} rendering."}
        if action == "recent_failures":
            snap = await network_snapshot(db, storage_path=root)
            failed = [j for j in snap["jobs"] if j["state"] in {"FAILED", "REPAIR"}]
            return {"status": "completed", "task": action,
                    "message": (f"{len(failed)} failed or repairing jobs in recent history."
                                if failed else "No failed jobs in recent history.")}
        channel_id = None
        if name:
            channels = (await db.scalars(select(NetworkChannel))).all()
            matches = [c for c in channels if c.name.casefold() == name]
            if len(matches) != 1:
                return {"status": "unsupported", "task": action,
                        "message": "I could not identify one matching channel."}
            channel_id = matches[0].id
        try:
            result = await apply_control(db, action, channel_id=channel_id, confirmed=confirmed)
        except (ValueError, LookupError):
            return {"status": "unsupported", "task": action,
                    "message": "That control is unavailable."}
        return {"status": "completed", "task": action, "result": result,
                "message": action.replace("_", " ").capitalize() + " completed. Public publishing remains off."}
