from pathlib import Path


def replace_once(
    path: Path,
    old: str,
    new: str,
) -> None:
    text = path.read_text(
        encoding="utf-8"
    )

    if new in text:
        print(
            f"{path}: already patched"
        )
        return

    if old not in text:
        raise RuntimeError(
            f"Expected text not found in {path}"
        )

    text = text.replace(
        old,
        new,
        1,
    )

    path.write_text(
        text,
        encoding="utf-8",
    )

    print(
        f"{path}: patched"
    )


registry = Path(
    "backend/services/agent_registry.py"
)

replace_once(
    registry,
    """from backend.services.agent_handlers.base import BaseAgentHandler
""",
    """from backend.services.agent_handlers.base import BaseAgentHandler
from backend.services.agent_handlers.system import SystemAgentHandler
""",
)

replace_once(
    registry,
    """    for handler_cls in BUILTIN_HANDLERS:
        registry.register_class(handler_cls)
    return registry
""",
    """    for handler_cls in BUILTIN_HANDLERS:
        registry.register_class(handler_cls)

    registry.register_class(
        SystemAgentHandler
    )

    return registry
""",
)


router = Path(
    "backend/services/voice/command_router.py"
)

replace_once(
    router,
    """    _CREATE_VIDEO_PATTERNS = (
""",
    """    _SYSTEM_STATUS_PATTERNS = (
        r"\\bjarvis\\s+status\\b",
        r"\\bsystem\\s+status\\b",
        r"\\bwhat(?:'s|\\s+is)\\s+(?:the\\s+)?progress\\b",
        r"\\bhow\\s+many\\s+videos?\\s+(?:have\\s+we\\s+made|are\\s+done|have\\s+been\\s+made|did\\s+we\\s+make)\\b",
        r"\\bhow\\s+(?:are|is)\\s+(?:the\\s+)?analytics\\b",
        r"\\bhow\\s+is\\s+(?:the\\s+)?channel\\s+doing\\b",
        r"\\bwhat\\s+happened\\s+in\\s+(?:the\\s+)?last\\s+production\\s+cycle\\b",
        r"\\bgive\\s+me\\s+(?:an?\\s+)?update\\b",
    )

    _CREATE_VIDEO_PATTERNS = (
""",
)

replace_once(
    router,
    """            ("youtube", "upload_video"),
            ("goal", "list_goals"),
""",
    """            ("youtube", "upload_video"),
            ("system", "get_status"),
            ("goal", "list_goals"),
""",
)

replace_once(
    router,
    """        if self._matches_any(
            transcript,
            self._CREATE_VIDEO_PATTERNS,
        ):
""",
    """        if self._matches_any(
            transcript,
            self._SYSTEM_STATUS_PATTERNS,
        ):
            candidates.append(
                (
                    "system",
                    "get_status",
                    None,
                )
            )

        if self._matches_any(
            transcript,
            self._CREATE_VIDEO_PATTERNS,
        ):
""",
)


executor = Path(
    "backend/services/voice/command_executor.py"
)

replace_once(
    executor,
    """            ("youtube", "upload_video"),
            ("goal", "list_goals"),
""",
    """            ("youtube", "upload_video"),
            ("system", "get_status"),
            ("goal", "list_goals"),
""",
)

print("PATCH COMPLETE")
